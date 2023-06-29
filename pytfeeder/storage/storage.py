from contextlib import contextmanager
import logging
from pathlib import Path
import sqlite3
from typing import List, Optional

from ..models import Entry
from .hooks import DBHooks


class Storage:
    def __init__(self, db_file: Path) -> None:
        self.db_file = db_file
        self.log = logging.getLogger()
        self.__init_db()

    def __init_db(self) -> None:
        if err := DBHooks(self.db_file).init_db():
            raise err

    @contextmanager
    def get_cursor(self):
        conn = sqlite3.connect(self.db_file)
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
    ) -> List[Entry]:
        entries: List[Entry] = []
        with self.get_cursor() as cursor:
            query = "SELECT id, title, updated, is_viewed FROM tb_entries {where} {channel_id} {and_} {timedelta} ORDER BY updated DESC {limit}".format(
                where="" if (not channel_id and not timedelta) else "WHERE",
                channel_id=f"channel_id = '{channel_id}'" if channel_id else "",
                timedelta=f"updated > '{timedelta}'" if timedelta else "",
                and_="AND" if (timedelta and channel_id) else "",
                limit=f"LIMIT {limit}" if limit else "",
            )
            self.log.debug(query)
            rows = cursor.execute(query).fetchall()
            self.log.debug("selected %d entries" % len(rows))
            for id, title, updated, is_viewed in rows:
                entries.append(
                    Entry(
                        id=id,
                        title=title,
                        updated=updated,
                        is_viewed=bool(is_viewed),
                    )
                )
            self.mark_entries_as_viewed(entries)
        return entries

    def mark_entries_as_viewed(self, entries: List[Entry]):
        with self.get_cursor() as cursor:
            update_query = "UPDATE tb_entries SET is_viewed = 1 WHERE id = ?"
            count = cursor.executemany(
                update_query, [(e.id,) for e in entries]
            ).rowcount
            if len(entries) != cursor.rowcount:
                self.log.warning(
                    "can't mark all selected entries as viewed (%d of %d)"
                    % (count, len(entries))
                )

    def add_entries(self, entries: List[Entry], channel_id: str) -> int:
        if not entries:
            return 0
        with self.get_cursor() as cursor:
            query = "INSERT OR IGNORE INTO tb_entries (id, title, updated, channel_id) VALUES (?, ?, ?, ?)"
            new_entries = [
                (entry.id, entry.title, entry.updated, channel_id) for entry in entries
            ]
            self.log.debug(f"{query}, entries count: {len(new_entries)}")
            return cursor.executemany(query, new_entries).rowcount

    def delete_all_entries(self) -> None:
        with self.get_cursor() as cursor:
            query = "DELETE FROM tb_entries WHERE is_viewed = 1"
            self.log.debug(query)
            cursor.execute(query)
            self.log.debug("%d entries removed" % cursor.rowcount)
