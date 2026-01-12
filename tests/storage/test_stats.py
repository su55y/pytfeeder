from pathlib import Path
import unittest

from pytfeeder.storage import Storage
from .. import mocks, utils


class TestStats(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        utils.setup_logging(filename=f"{Path(__file__).name}.log")
        cls.db_file = utils.temp_storage_path()
        cls.stor = Storage(cls.db_file)

        cls.sample_entries = mocks.sample_entries
        cls.another_entry = mocks.another_sample_entries[0]
        cls.entries = cls.sample_entries + [cls.another_entry]

        assert cls.stor.add_entries(cls.entries) == len(cls.entries)
        cls.stor.mark_entry_as_watched(id=cls.sample_entries[0].id)

    @classmethod
    def tearDownClass(cls):
        if cls.db_file.exists():
            cls.db_file.unlink()

    def test_stats(self):
        stats = self.stor.select_stats()
        self.assertIsInstance(stats, list)
        self.assertEqual(len(stats), 2)

        self.assertListEqual(
            stats,
            [
                (
                    self.sample_entries[0].channel_id,
                    len(self.sample_entries),
                    len(self.sample_entries),
                    len(self.sample_entries) - 1,
                    0,
                ),
                (self.another_entry.channel_id, 1, 1, 1, 0),
            ],
        )
