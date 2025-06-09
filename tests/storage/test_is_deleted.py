from pathlib import Path
import unittest

from pytfeeder.storage import Storage
from .. import mocks, utils


class IsDeletedTest(unittest.TestCase):
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

    def test_is_deleted(self):
        self.assertEqual(self.stor.select_entries_count(), 1)
        self.assertFalse(self.stor.select_entries()[0].is_deleted)
        self.assertTrue(self.stor.mark_entry_as_deleted(id=self.entry.id))
        self.assertEqual(len(self.stor.select_entries()), 0)
        self.assertEqual(self.stor.select_entries_count(is_deleted=True), 1)
