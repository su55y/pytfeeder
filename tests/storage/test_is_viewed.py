from pathlib import Path
import unittest

from pytfeeder.storage import Storage
from .. import mocks, utils


class IsViewedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        utils.setup_logging(filename=f"{Path(__file__).name}.log")
        cls.db_file = utils.temp_storage_path()
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
