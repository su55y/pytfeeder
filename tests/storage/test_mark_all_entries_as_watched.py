from pathlib import Path
import unittest

from pytfeeder.storage import Storage
from .. import mocks, utils


class TestStats(unittest.TestCase):
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

    def test_mark_all_entries_as_watched(self):
        self.assertEqual(
            self.stor.add_entries(mocks.sample_entries),
            len(mocks.sample_entries),
        )
        self.assertEqual(
            self.stor.select_entries_count(include_watched=False),
            len(mocks.sample_entries),
        )
        self.stor.mark_all_entries_as_watched()
        self.assertEqual(self.stor.select_entries_count(include_watched=False), 0)
