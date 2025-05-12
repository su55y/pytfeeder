import datetime as dt
from pathlib import Path
import unittest

from pytfeeder import Storage
from . import mocks, utils


class StorageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        utils.setup_logging(filename=f"{Path(__file__).name}.log")
        cls.db_file = Path("/tmp/test_storage.db")
        if cls.db_file.exists():
            cls.db_file.unlink()
        cls.stor = Storage(cls.db_file)

    @classmethod
    def tearDownClass(cls):
        if cls.db_file.exists():
            cls.db_file.unlink()

    def test1_insert(self):
        self.assertEqual(
            self.stor.add_entries(mocks.sample_entries),
            len(mocks.sample_entries),
        )

    def test2_select_entries(self):
        entries = self.stor.select_entries(mocks.sample_channel.channel_id)
        self.assertEqual(entries, mocks.sample_entries)

    def test2_select_not_found(self):
        entries = self.stor.select_entries(channel_id="-")
        self.assertEqual(len(entries), 0)

    def test3_select_by_timedelta(self):
        td = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=24)
        tds = td.isoformat(sep="T", timespec="seconds")
        self.assertEqual(len(self.stor.select_entries(timedelta=tds)), 1)

    def test3_insert_duplicate(self):
        count = self.stor.add_entries(mocks.sample_entries)
        self.assertEqual(count, 0)
