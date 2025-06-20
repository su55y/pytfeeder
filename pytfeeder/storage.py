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
        self.log.debug(f"Connecting to {self.db_file!r}")
        conn = sqlite3.connect(self.db_file)
        if self.log.level == logging.DEBUG:
            conn.set_trace_callback(self.log.debug)

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
                self.log.debug(f"Applying {migration.name}")
                cur.executescript("BEGIN;" + migration.read_text())
            except Exception as e:
                self.log.error(f"Failed migration {migration.name}: {e}")
                cur.execute("ROLLBACK")
                conn.close()
                raise StorageError(f"Migration failed ({migration.name})") from e
            else:
                cur.execute("COMMIT")
        conn.close()

    @contextmanager
    def get_cursor(self):
        conn = sqlite3.connect(self.db_file, detect_types=sqlite3.PARSE_DECLTYPES)
        if self.log.level == logging.DEBUG:
            conn.set_trace_callback(self.log.debug)

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
            self.log.debug(f"{len(new_entries) = }")
            rowcount = cursor.executemany(query, new_entries).rowcount
            self.log.debug(f"{rowcount = }")
            return rowcount

    def fetchall_rows(
        self,
        query: str,
        params: tuple[Any, ...] | dict[str, Any] | None = None,
    ) -> list[tuple]:
        with self.get_cursor() as cursor:
            self.log.debug(f"{params = !r}")
            if params:
                rows = cursor.execute(query, params).fetchall()
            else:
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
        params: dict[str, Any] = {}

        and_channel_id = ""
        if channel_id:
            params["channel_id"] = channel_id
            and_channel_id = "AND channel_id=:channel_id"

        and_timedelta = ""
        if timedelta:
            params["timedelta"] = timedelta
            and_timedelta = "AND published > :timedelta"

        and_in_channels = ""
        if in_channels is not None:
            markers = []
            for i, c in enumerate(in_channels):
                cid = f"cid{i}"
                params[cid] = c.channel_id
                markers.append(f":{cid}")
            and_in_channels = f"AND channel_id IN ({','.join(markers)})"

        and_unwatched_first = "is_viewed," if unwatched_first else ""

        and_limit = ""
        if limit:
            params["limit"] = limit
            and_limit = "LIMIT :limit"

        query = f"""
        SELECT id, title, published, channel_id, is_viewed, is_deleted
        FROM {TB_ENTRIES}
        WHERE is_deleted = 0 {and_channel_id} {and_timedelta} {and_in_channels}
        ORDER BY {and_unwatched_first} published DESC {and_limit}"""

        rows = self.fetchall_rows(query, params=params)
        if rows is None:
            return entries

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

    def select_channels_stats(self) -> dict[str, tuple[int, int]]:
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

    def select_channels_with_deleted(self) -> list[tuple[str, int]]:
        query = f"""
        SELECT channel_id, SUM(is_deleted = 1) as c1
        FROM {TB_ENTRIES}
        WHERE is_deleted = 1
        GROUP BY channel_id
        ORDER BY c1 DESC;"""
        return self.fetchall_rows(query)

    def restore_channel(self, c: Channel) -> int:
        query = f"""
        UPDATE {TB_ENTRIES}
        SET is_deleted = 0
        WHERE channel_id = ?;
        """
        return self.update_rows(query, (c.channel_id,))

    def select_entries_count(
        self,
        *,
        channel_id: str | None = None,
        is_deleted: bool | None = None,
        is_watched: bool | None = None,
        in_channels: list[Channel] | None = None,
    ) -> int:
        params_list: list[Any] = []

        where_is_deleted = "is_deleted IN (0, 1)"
        if is_deleted is not None:
            where_is_deleted = "is_deleted = ?"
            params_list.append(is_deleted)

        and_is_viewed = ""
        if is_watched is not None:
            and_is_viewed = "AND is_viewed = ?"
            params_list.append(is_watched)

        and_for_channel = ""
        if channel_id:
            and_for_channel = "AND channel_id = ?"
            params_list.append(channel_id)

        and_in_channels = ""
        if in_channels is not None and len(in_channels):
            params_list += [c.channel_id for c in in_channels]
            and_in_channels = f"AND channel_id IN ({','.join('?'*len(in_channels))})"

        query = f"""
        SELECT COUNT(*) FROM {TB_ENTRIES} 
        WHERE {where_is_deleted} {and_is_viewed} {and_for_channel} {and_in_channels}"""
        params = tuple(params_list)

        with self.get_cursor() as cursor:
            self.log.debug(f"{params = !r}")
            (count,) = cursor.execute(query, params).fetchone()
            self.log.debug(f"{count = }")
            return count

    def update_rows(self, query: str, params: tuple[Any, ...] | None = None) -> int:
        with self.get_cursor() as cursor:
            self.log.debug(f"{params = !r}")
            if params is None:
                rowcount = cursor.execute(query).rowcount
            else:
                rowcount = cursor.execute(query, params).rowcount
            self.log.debug(f"{rowcount = }")
            return rowcount

    def mark_entry_as_watched(self, id: str, unwatched: bool = False) -> None:
        is_viewed = 0 if unwatched else 1
        query = f"UPDATE {TB_ENTRIES} SET is_viewed = ? WHERE id = ?"
        rowcount = self.update_rows(query, params=(is_viewed, id))
        if rowcount != 1:
            self.log.warning(f"{rowcount = } for mark_entry_as_watched({id = !r})")

    def mark_entry_as_deleted(self, id: str) -> bool:
        query = f"UPDATE {TB_ENTRIES} SET is_deleted = 1 WHERE id = ?"
        rowcount = self.update_rows(query, params=(id,))
        if rowcount != 1:
            self.log.warning(f"{rowcount = } for mark_entry_as_deleted({id = !r})")
        return rowcount == 1

    def mark_channel_entries_as_deleted(self, channel_id: str) -> int:
        query = f"UPDATE {TB_ENTRIES} SET is_deleted = 1 WHERE channel_id = ? AND is_deleted != 1"
        return self.update_rows(query, params=(channel_id,))

    def mark_channel_entries_as_watched(
        self, channel_id: str, unwatched: bool = False
    ) -> None:
        is_viewed = 0 if unwatched else 1
        query = f"UPDATE {TB_ENTRIES} SET is_viewed = ? WHERE channel_id = ?"
        _ = self.update_rows(query, params=(is_viewed, channel_id))

    def mark_all_entries_as_watched(self, unwatched: bool = False) -> None:
        is_viewed = 0 if unwatched else 1
        query = f"UPDATE {TB_ENTRIES} SET is_viewed = ?"
        _ = self.update_rows(query, params=(is_viewed,))

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
        return self.update_rows(query)

    def purge_deleted_entries(self) -> None:
        query = f"DELETE FROM {TB_ENTRIES} WHERE is_deleted = 1"
        _ = self.update_rows(query)

    def mark_watched_as_deleted(self) -> None:
        query = f"UPDATE {TB_ENTRIES} SET is_deleted = 1 WHERE is_viewed = 1"
        _ = self.update_rows(query)

    def delete_inactive_channels(self, active_channels: list[Channel]) -> int:
        if len(active_channels) == 0:
            return 0
        markers = ",".join("?" * len(active_channels))
        channels_ids = tuple(c.channel_id for c in active_channels)
        query = f"DELETE FROM {TB_ENTRIES} WHERE channel_id NOT IN ({markers})"
        return self.update_rows(query, params=channels_ids)

    def execute_vacuum(self) -> None:
        query = "VACUUM"
        with self.get_cursor() as cursor:
            cursor.execute(query)
