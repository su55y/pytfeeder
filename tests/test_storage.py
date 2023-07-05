from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
import unittest

from pytfeeder.storage import Storage
from .mocks import sample_channel, sample_entries

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
            self.stor.add_entries(sample_entries, sample_channel.channel_id),
            len(sample_entries),
        )

    def test2_select_entries(self):
        entries = self.stor.select_entries(sample_channel.channel_id)
        self.assertEqual(entries, sample_entries)

    def test2_select_not_found(self):
        entries = self.stor.select_entries(channel_id="-")
        self.assertEqual(len(entries), 0)

    def test3_select_by_timedelta(self):
        td = str(datetime.now(timezone.utc) - timedelta(hours=24))
        self.assertEqual(len(self.stor.select_entries(timedelta=td)), 1)

    def test3_insert_duplicate(self):
        count = self.stor.add_entries(sample_entries, sample_channel.channel_id)
        self.assertEqual(count, 0)

    def test3_mark_as_viewed(self):
        self.stor.mark_entry_as_viewed(id=sample_entries[0].id)
        self.assertTrue(self.stor.select_entries()[0])

    def test4_delete(self):
        self.stor.delete_all_entries(force=True)
        self.assertEqual(len(self.stor.select_entries()), 0)
