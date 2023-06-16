from pathlib import Path
import sqlite3
from typing import Optional

from .queries import QUERIES


class DBHooks:
    def __init__(self, db_file: Path) -> None:
        self.db_file = db_file

    def init_db(self) -> Optional[Exception]:
        if not self.db_file.exists():
            for query in QUERIES:
                if err := self._execute(query):
                    return err

    def drop_db(self) -> Optional[Exception]:
        if not self.db_file.exists() or not self.db_file.is_file():
            return Exception(f"{self.db_file} not exists or not a file")
        try:
            self.db_file.unlink()
        except Exception as e:
            return e

    def _execute(self, query: str) -> Optional[Exception]:
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.execute(query)
        except Exception as e:
            return e
