from contextlib import contextmanager
import datetime as dt
import logging
from pathlib import Path
import sqlite3
from typing import List, Optional, Tuple
from .models import Entry

TB_ENTRIES = "tb_entries"


def join_split(s: str) -> str:
    return " ".join(s.split())


def tb_entries_sql(if_not_exists=False) -> str:
    return """CREATE TABLE {if_not_exists} {tb_entries}(
        id TEXT NOT NULL CHECK(length(id) == 11) PRIMARY KEY,
        title TEXT NOT NULL,
        published DATETIME NOT NULL,
        channel_id TEXT NOT NULL,
        is_viewed TINYINT NOT NULL DEFAULT 0
    )""".format(
        if_not_exists="IF NOT EXISTS" if if_not_exists else "",
        tb_entries=TB_ENTRIES,
    )


class Storage:
    def __init__(self, db_file: Path) -> None:
        self.db_file = db_file
        self.log = logging.getLogger()
        sqlite3.register_adapter(dt.datetime, lambda v: v.isoformat())
        self.__init_db()

    def __init_db(self) -> None:
        self.log.debug("__init_db")
        conn = sqlite3.connect(self.db_file)
        cur = conn.cursor()
        cur.execute(tb_entries_sql(if_not_exists=True))
        row = cur.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (TB_ENTRIES,),
        ).fetchone()
        if row is None or len(row) != 1:
            self.log.error(f"Cannot verify db integrity ({row = !r})")
            raise Exception(f"{TB_ENTRIES!r} not found in db {self.db_file!r}")

        (sql,) = row
        assert join_split(sql) == join_split(tb_entries_sql()), "Invalid db"

        conn.commit()

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

    def select_entries(
        self,
        channel_id: Optional[str] = None,
        limit: Optional[int] = None,
        timedelta: Optional[str] = None,
        unviewed_first: Optional[bool] = None,
    ) -> List[Entry]:
        entries: List[Entry] = []
        with self.get_cursor() as cursor:
            query = "SELECT id, title, published, channel_id, is_viewed FROM tb_entries {where} {channel_id} {and_} {timedelta} ORDER BY {unviewed_first} published DESC {limit}".format(
                where="" if (not channel_id and not timedelta) else "WHERE",
                channel_id=f"channel_id = '{channel_id}'" if channel_id else "",
                and_="AND" if (timedelta and channel_id) else "",
                timedelta=f"published > '{timedelta}'" if timedelta else "",
                unviewed_first="is_viewed," if unviewed_first else "",
                limit=f"LIMIT {limit}" if limit else "",
            )
            self.log.debug(query)
            rows = cursor.execute(query).fetchall()
            self.log.debug("selected %d entries" % len(rows))
            for id, title, published, c_id, is_viewed in rows:
                entries.append(
                    Entry(
                        id=id,
                        title=title,
                        published=dt.datetime.fromisoformat(published),
                        channel_id=c_id,
                        is_viewed=bool(is_viewed),
                    )
                )
        return entries

    def select_unviewed(self, channel_id: Optional[str] = None) -> int:
        with self.get_cursor() as cursor:
            query = "SELECT COUNT(*) FROM tb_entries WHERE is_viewed = 0 {for_channel}".format(
                for_channel=f"AND channel_id = '{channel_id}'" if channel_id else ""
            )
            self.log.debug(query)
            count, *_ = cursor.execute(query).fetchone()
            return count

    def select_entries_count(self, channel_id: Optional[str] = None) -> int:
        with self.get_cursor() as cursor:
            query = "SELECT COUNT(*) FROM tb_entries {for_channel}".format(
                for_channel=f"WHERE channel_id = '{channel_id}'" if channel_id else ""
            )
            self.log.debug(query)
            count, *_ = cursor.execute(query).fetchone()
            return count

    def mark_entry_as_viewed(self, id: str, unviewed: bool = False) -> None:
        value = 0 if unviewed else 1
        with self.get_cursor() as cursor:
            query = f"UPDATE tb_entries SET is_viewed = {value} WHERE id = ?"
            self.log.debug("%s, id: %s" % (query, id))
            count = cursor.execute(query, (id,)).rowcount
            if count != 1:
                self.log.warning("rowcount != 1 for mark_entry_as_viewed(%s)" % id)

    def mark_channel_entries_as_viewed(
        self, channel_id: str, unviewed: bool = False
    ) -> None:
        value = 0 if unviewed else 1
        with self.get_cursor() as cursor:
            query = f"UPDATE tb_entries SET is_viewed = {value} WHERE channel_id = ?"
            self.log.debug("%s, channel_id: %s" % (query, channel_id))
            cursor.execute(query, (channel_id,))

    def mark_all_entries_as_viewed(self, unviewed: bool = False):
        value = 0 if unviewed else 1
        with self.get_cursor() as cursor:
            query = f"UPDATE tb_entries SET is_viewed = {value}"
            self.log.debug(query)
            cursor.execute(query)

    def add_entries(self, entries: List[Entry]) -> int:
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

    def delete_all_entries(self, force: bool = False) -> None:
        """Removes entries from DB
        Args:
            force (bool, default False): removes only entries with `is_viewed = 1` if False
        """
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

    def select_stats(self) -> List[Tuple[str, int, int]]:
        with self.get_cursor() as cursor:
            query = "SELECT channel_id, COUNT(channel_id) AS c1, SUM(is_viewed = 0) FROM tb_entries GROUP BY channel_id ORDER BY c1 DESC;"
            self.log.debug(query)
            rows = cursor.execute(query).fetchall()
            self.log.debug("selected %d rows" % len(rows))
            return rows
