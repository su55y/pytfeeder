import logging
from pathlib import Path
import unittest

from pytfeeder.storage import Storage
from .. import mocks

logging.basicConfig(level=logging.DEBUG, filename="/tmp/test_storage.log")


class IsViewedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_file = Path("/tmp/test_storage.db")
        if cls.db_file.exists():
            cls.db_file.unlink()
        cls.stor = Storage(cls.db_file)
        cls.entry = mocks.sample_entries[0]
        assert cls.stor.add_entries([cls.entry]) == 1, "Insert test entry failed"

    @classmethod
    def tearDownClass(cls):
        if cls.db_file.exists():
            cls.db_file.unlink()

    def test_is_viewed_1(self):
        self.assertEqual(self.stor.select_entries()[0].is_viewed, False)
        self.stor.mark_entry_as_watched(id=self.entry.id)
        self.assertEqual(self.stor.select_entries()[0].is_viewed, True)

    def test_is_viewed_2(self):
        self.assertEqual(self.stor.select_entries()[0].is_viewed, True)
        self.stor.mark_entry_as_watched(id=self.entry.id, unwatched=True)
        self.assertEqual(self.stor.select_entries()[0].is_viewed, False)
