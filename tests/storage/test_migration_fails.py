from pathlib import Path
import sqlite3
import unittest

from pytfeeder.storage import Storage, StorageError, TB_ENTRIES
from .. import utils


class TestMigrationFails(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        utils.setup_logging(filename=f"{Path(__file__).name}.log")
        cls.db_file = Path("/tmp/test_storage.db")
        if cls.db_file.exists():
            cls.db_file.unlink()

        conn = sqlite3.connect(cls.db_file)
        cur = conn.cursor()
        cur.execute(f"CREATE TABLE {TB_ENTRIES} (test TINYINT NOT NULL DEFAULT 0)")
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        if cls.db_file.exists():
            cls.db_file.unlink()

    def test_fail_on_outdated_db(self):
        import logging

        log = logging.getLogger()
        log.addHandler(logging.NullHandler())
        with self.assertRaises(StorageError):
            _ = Storage(self.db_file, log=log)
