from contextlib import contextmanager
import datetime as dt
from importlib import resources
import logging
from pathlib import Path
import sqlite3

from .models import Entry
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
        with self.get_cursor() as cursor:
            query = "INSERT OR IGNORE INTO tb_entries (id, title, published, channel_id) VALUES (?, ?, ?, ?)"
            new_entries = [
                (entry.id, entry.title, entry.published, entry.channel_id)
                for entry in entries
            ]
            self.log.debug(f"{query}, entries count: {len(new_entries)}")
            return cursor.executemany(query, new_entries).rowcount

    def select_entries(
        self,
        channel_id: str | None = None,
        limit: int | None = None,
        timedelta: str | None = None,
        unwatched_first: bool | None = None,
    ) -> list[Entry]:
        entries: list[Entry] = []
        with self.get_cursor() as cursor:
            query = """
            SELECT id, title, published, channel_id, is_viewed, is_deleted
            FROM tb_entries
            WHERE is_deleted = 0 {and_channel_id} {and_timedelta}
            ORDER BY {unwatched_first} published DESC {limit}""".format(
                and_channel_id=f"AND channel_id = '{channel_id}'" if channel_id else "",
                and_timedelta=f"AND published > '{timedelta}'" if timedelta else "",
                unwatched_first="is_viewed," if unwatched_first else "",
                limit=f"LIMIT {limit}" if limit else "",
            )
            self.log.debug(query)
            rows = cursor.execute(query).fetchall()
            self.log.debug("selected %d entries" % len(rows))
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

    def select_unwatched(self, channel_id: str | None = None) -> int:
        with self.get_cursor() as cursor:
            query = """
            SELECT COUNT(*) FROM tb_entries
            WHERE is_viewed = 0 AND is_deleted = 0 {for_channel}""".format(
                for_channel=f"AND channel_id = '{channel_id}'" if channel_id else ""
            )
            self.log.debug(query)
            count, *_ = cursor.execute(query).fetchone()
            return count

    def select_entries_count(self, channel_id: str | None = None) -> int:
        with self.get_cursor() as cursor:
            query = "SELECT COUNT(*) FROM tb_entries {for_channel}".format(
                for_channel=f"WHERE channel_id = '{channel_id}'" if channel_id else ""
            )
            self.log.debug(query)
            count, *_ = cursor.execute(query).fetchone()
            return count

    def select_stats(self) -> list[tuple[str, int, int]]:
        with self.get_cursor() as cursor:
            query = """
            SELECT channel_id, COUNT(channel_id) AS c1, SUM(is_viewed = 0 AND is_deleted = 0)
            FROM tb_entries
            GROUP BY channel_id ORDER BY c1 DESC;"""
            self.log.debug(query)
            rows = cursor.execute(query).fetchall()
            self.log.debug("selected %d rows" % len(rows))
            return rows

    def mark_entry_as_watched(self, id: str, unwatched: bool = False) -> None:
        value = 0 if unwatched else 1
        with self.get_cursor() as cursor:
            query = f"UPDATE tb_entries SET is_viewed = {value} WHERE id = ?"
            self.log.debug("%s, id: %s" % (query, id))
            count = cursor.execute(query, (id,)).rowcount
            if count != 1:
                self.log.warning("rowcount != 1 for mark_entry_as_watched(%s)" % id)

    def mark_channel_entries_as_watched(
        self, channel_id: str, unwatched: bool = False
    ) -> None:
        value = 0 if unwatched else 1
        with self.get_cursor() as cursor:
            query = f"UPDATE tb_entries SET is_viewed = {value} WHERE channel_id = ?"
            self.log.debug("%s, channel_id: %s" % (query, channel_id))
            cursor.execute(query, (channel_id,))

    def mark_all_entries_as_watched(self, unwatched: bool = False):
        value = 0 if unwatched else 1
        with self.get_cursor() as cursor:
            query = f"UPDATE tb_entries SET is_viewed = {value}"
            self.log.debug(query)
            cursor.execute(query)

    def mark_entry_as_deleted(self, id: str) -> bool:
        with self.get_cursor() as cursor:
            query = f"UPDATE tb_entries SET is_deleted = 1 WHERE id = ?"
            self.log.debug("%s, id: %s" % (query, id))
            count = cursor.execute(query, (id,)).rowcount
            if count != 1:
                self.log.warning("rowcount != 1 for mark_entry_as_deleted(%s)" % id)
            return count == 1

    def delete_all_entries(self, force: bool = False) -> None:
        with self.get_cursor() as cursor:
            query = "DELETE FROM tb_entries {}".format(
                "" if force else " WHERE is_viewed = 1"
            )
            self.log.debug(query)
            cursor.execute(query)
            self.log.debug("%d entries removed" % cursor.rowcount)

    def delete_inactive_channels(self, channels_list_str: str) -> None:
        with self.get_cursor() as cursor:
            query = (
                "DELETE FROM tb_entries WHERE channel_id NOT IN (%s)"
                % channels_list_str
            )
            self.log.debug(query)
            cursor.execute(query)
            self.log.debug("%d entries removed" % cursor.rowcount)
