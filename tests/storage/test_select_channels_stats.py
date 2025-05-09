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

        cls.sample_entries = mocks.sample_entries
        cls.another_entry = mocks.another_sample_entries[0]
        cls.entries = cls.sample_entries + [cls.another_entry]

        assert cls.stor.add_entries(cls.entries) == len(cls.entries)
        cls.stor.mark_entry_as_watched(id=cls.sample_entries[0].id)
        cls.stor.mark_entry_as_deleted(id=cls.sample_entries[1].id)

    @classmethod
    def tearDownClass(cls):
        if cls.db_file.exists():
            cls.db_file.unlink()

    def test_select_all_unwatched(self):
        stats = self.stor.select_all_unwatched()
        c1, u1 = stats[self.sample_entries[0].channel_id]
        self.assertEqual(c1, len(self.sample_entries) - 1)
        self.assertEqual(u1, len(self.sample_entries) - 2)

        c2, u2 = stats[self.another_entry.channel_id]
        self.assertEqual(c2, 1)
        self.assertEqual(u2, 1)
