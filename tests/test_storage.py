from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
import unittest

from pytfeeder.storage import Storage
from . import mocks

logging.basicConfig(level=logging.DEBUG, filename="/tmp/test_storage.log")


class StorageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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
        td = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(
            sep="T", timespec="seconds"
        )
        self.assertEqual(len(self.stor.select_entries(timedelta=td)), 1)

    def test3_insert_duplicate(self):
        count = self.stor.add_entries(mocks.sample_entries)
        self.assertEqual(count, 0)

    def test5_delete_inactive(self):
        count = self.stor.add_entries(mocks.another_sample_entries)
        self.assertEqual(count, len(mocks.another_sample_entries))
        self.stor.delete_inactive_channels(
            ", ".join(f"{c.channel_id!r}" for c in mocks.sample_entries)
        )
        self.assertEqual(self.stor.select_entries(), mocks.sample_entries)

    def test6_delete(self):
        self.stor.delete_all_entries(force=True)
        self.assertEqual(len(self.stor.select_entries()), 0)
