from contextlib import contextmanager
import datetime as dt
from importlib import resources
import logging
from pathlib import Path
import sqlite3
from typing import Any

from .models import Channel, Entry
import pytfeeder.migrations as migrations_dir

TB_ENTRIES = "tb_entries"


class StorageError(Exception):
    pass


class Storage:
    def __init__(self, db_file: Path, log: logging.Logger | None = None) -> None:
        self.db_file = db_file
        self.log = log or logging.getLogger()
        sqlite3.register_adapter(dt.datetime, lambda v: v.isoformat())
        self.__init_db()

    def __init_db(self) -> None:
        self.log.debug(f"connecting to {self.db_file!r}")
        conn = sqlite3.connect(self.db_file)
        (current_version,) = next(conn.cursor().execute("PRAGMA user_version"), (0,))
        self.log.debug(f"{current_version = }")

        migrations = list(resources.files(migrations_dir).iterdir())
        self.log.debug(f"migrations = [{', '.join(f'{m.name!r}' for m in migrations)}]")

        if len(migrations) == 0:
            raise StorageError(
                f"Migration files not found in {migrations_dir = } ({migrations = })"
            )

        if current_version < 0 or len(migrations) < current_version:
            raise StorageError(
                f"Unexpected PRAGMA user_version = {current_version}, should be 0 <= user_version <= {len(migrations)}"
            )

        for migration in migrations[current_version:]:
            cur = conn.cursor()
            try:
                self.log.debug("applying %s", migration.name)
                cur.executescript("begin;" + migration.read_text())
            except Exception as e:
                self.log.error("failed migration %s: %s", migration.name, e)
                cur.execute("rollback")
                raise StorageError(f"Migration failed ({migration.name})") from e
            else:
                cur.execute("commit")
        conn.close()

    @contextmanager
    def get_cursor(self):
        conn = sqlite3.connect(self.db_file, detect_types=sqlite3.PARSE_DECLTYPES)
        try:
            yield conn.cursor()
        except Exception as e:
            self.log.error(e)
        else:
            conn.commit()
        finally:
            conn.close()

    def add_entries(self, entries: list[Entry]) -> int:
        if not entries:
            return 0
        query = f"INSERT OR IGNORE INTO {TB_ENTRIES} (id, title, published, channel_id) VALUES (?, ?, ?, ?)"
        with self.get_cursor() as cursor:
            new_entries = [
                (entry.id, entry.title, entry.published, entry.channel_id)
                for entry in entries
            ]
            self.log.debug(f"{query}, {len(new_entries) = }")
            return cursor.executemany(query, new_entries).rowcount

    def fetchall_rows(self, query: str) -> list[tuple]:
        with self.get_cursor() as cursor:
            self.log.debug(query)
            rows = cursor.execute(query).fetchall()
            self.log.debug(f"{len(rows) = }")
            return rows

    def select_entries(
        self,
        channel_id: str | None = None,
        limit: int | None = None,
        timedelta: str | None = None,
        unwatched_first: bool | None = None,
        in_channels: list[Channel] | None = None,
    ) -> list[Entry]:
        entries: list[Entry] = []
        in_channels_value = ""
        if in_channels is not None:
            channels_ids = ", ".join(f"'{c.channel_id}'" for c in in_channels)
            in_channels_value = f"AND channel_id IN ({channels_ids})"
        query = """
        SELECT id, title, published, channel_id, is_viewed, is_deleted
        FROM {tb_entries}
        WHERE is_deleted = 0 {and_channel_id} {and_timedelta} {and_in_channels}
        ORDER BY {unwatched_first} published DESC {limit}""".format(
            tb_entries=TB_ENTRIES,
            and_channel_id=f"AND channel_id = '{channel_id}'" if channel_id else "",
            and_timedelta=f"AND published > '{timedelta}'" if timedelta else "",
            and_in_channels=in_channels_value,
            unwatched_first="is_viewed," if unwatched_first else "",
            limit=f"LIMIT {limit}" if limit else "",
        )
        rows = self.fetchall_rows(query)
        for id, title, published, c_id, is_viewed, is_deleted in rows:
            entries.append(
                Entry(
                    id=id,
                    title=title,
                    published=dt.datetime.fromisoformat(published),
                    channel_id=c_id,
                    is_viewed=bool(is_viewed),
                    is_deleted=bool(is_deleted),
                )
            )
        return entries

    def select_all_unwatched(self) -> dict[str, tuple[int, int]]:
        query = f"""
        SELECT channel_id, SUM(is_deleted = 0), SUM(is_viewed = 0 AND is_deleted = 0)
        FROM {TB_ENTRIES}
        GROUP BY channel_id;"""
        rows = self.fetchall_rows(query)
        return {c_id: (count, unwatched) for c_id, count, unwatched in rows}

    def select_stats(self) -> list[tuple[str, int, int, int]]:
        query = f"""
        SELECT channel_id, COUNT(channel_id) AS c1,
        SUM(is_viewed = 0 AND is_deleted = 0), SUM(is_deleted = 1)
        FROM {TB_ENTRIES} 
        GROUP BY channel_id ORDER BY c1 DESC;"""
        return self.fetchall_rows(query)

    def select_count(self, query: str) -> int:
        with self.get_cursor() as cursor:
            self.log.debug(query)
            (count,) = cursor.execute(query).fetchone()
            self.log.debug(f"{count = }")
            return count

    def select_unwatched_count(self, channel_id: str | None = None) -> int:
        query = """
        SELECT COUNT(*) FROM {tb_entries}
        WHERE is_viewed = 0 AND is_deleted = 0 {for_channel}""".format(
            tb_entries=TB_ENTRIES,
            for_channel=f"AND channel_id = '{channel_id}'" if channel_id else "",
        )
        return self.select_count(query)

    def select_entries_count(
        self,
        channel_id: str | None = None,
        exclude_deleted: bool = False,
    ) -> int:
        query = """
        SELECT COUNT(*) FROM {tb_entries} {where} {for_channel} {and_} {is_deleted}""".format(
            tb_entries=TB_ENTRIES,
            where="WHERE" if channel_id or exclude_deleted else "",
            for_channel=f"channel_id = '{channel_id}'" if channel_id else "",
            is_deleted="is_deleted = 0" if exclude_deleted else "",
            and_="AND" if channel_id and exclude_deleted else "",
        )
        return self.select_count(query)

    def update_row(self, query: str, params: tuple[Any, ...]) -> bool:
        with self.get_cursor() as cursor:
            self.log.debug(f"{query}, {params = !r}")
            rowcount = cursor.execute(query, params).rowcount
            self.log.debug(f"{rowcount = }")
            return rowcount == 1

    def mark_entry_as_watched(self, id: str, unwatched: bool = False) -> None:
        is_viewed = 0 if unwatched else 1
        query = f"UPDATE {TB_ENTRIES} SET is_viewed = ? WHERE id = ?"
        if not self.update_row(query, (is_viewed, id)):
            self.log.warning(f"rowcount = 0 for mark_entry_as_watched({id = !r})")

    def mark_entry_as_deleted(self, id: str) -> bool:
        query = f"UPDATE {TB_ENTRIES} SET is_deleted = 1 WHERE id = ?"
        ok = self.update_row(query, (id,))
        if not ok:
            self.log.warning(f"rowcount = 0 for mark_entry_as_deleted({id = !r})")
        return ok

    def update_rows(self, query: str, params: tuple[Any, ...]) -> None:
        with self.get_cursor() as cursor:
            self.log.debug(f"{query}, {params = !r}")
            rowcount = cursor.execute(query, params).rowcount
            self.log.debug(f"{rowcount = }")

    def mark_channel_entries_as_watched(
        self, channel_id: str, unwatched: bool = False
    ) -> None:
        is_viewed = 0 if unwatched else 1
        query = f"UPDATE {TB_ENTRIES} SET is_viewed = ? WHERE channel_id = ?"
        self.update_rows(query, (is_viewed, channel_id))

    def mark_all_entries_as_watched(self, unwatched: bool = False) -> None:
        is_viewed = 0 if unwatched else 1
        query = f"UPDATE {TB_ENTRIES} SET is_viewed = ?"
        self.update_rows(query, (is_viewed,))

    def delete_rows(self, query: str) -> int:
        with self.get_cursor() as cursor:
            self.log.debug(query)
            rowcount = cursor.execute(query).rowcount
            self.log.debug(f"{rowcount = }")
            return rowcount

    def delete_old_entries(self) -> int:
        query = f"""
        DELETE FROM {TB_ENTRIES}
        WHERE is_deleted = 1 AND id NOT IN (
            SELECT id
            FROM {TB_ENTRIES} AS e
            WHERE (
                SELECT COUNT(*)
                FROM {TB_ENTRIES} AS e2
                WHERE e2.channel_id = e.channel_id AND e2.published > e.published
            ) < 15
        )
        """
        return self.delete_rows(query)

    def purge_deleted_entries(self) -> None:
        query = f"DELETE FROM {TB_ENTRIES} WHERE is_deleted = 1"
        _ = self.delete_rows(query)

    def mark_watched_as_deleted(self) -> None:
        query = f"UPDATE {TB_ENTRIES} SET is_deleted = 1 WHERE is_viewed = 1"
        _ = self.delete_rows(query)

    def delete_inactive_channels(self, active_channels: list[Channel]) -> None:
        if len(active_channels) == 0:
            return
        channels_list = ", ".join(f"'{c.channel_id}'" for c in active_channels)
        query = f"DELETE FROM {TB_ENTRIES} WHERE channel_id NOT IN ({channels_list})"
        _ = self.delete_rows(query)

    def execute_vacuum(self) -> None:
        query = "VACUUM"
        with self.get_cursor() as cursor:
            self.log.debug(query)
            cursor.execute(query)
