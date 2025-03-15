import logging
from pathlib import Path
import unittest

from pytfeeder.storage import Storage
from .. import mocks

logging.basicConfig(level=logging.DEBUG, filename="/tmp/test_storage.log")


class TestStats(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_file = Path("/tmp/test_storage.db")
        if cls.db_file.exists():
            cls.db_file.unlink()

        cls.stor = Storage(cls.db_file)

        cls.sample_entries = mocks.sample_entries
        cls.another_entry = mocks.another_sample_entries[0]
        cls.entries = cls.sample_entries + [cls.another_entry]

        assert cls.stor.add_entries(cls.entries) == len(cls.entries)
        cls.stor.mark_entry_as_viewed(id=cls.sample_entries[0].id)

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
                    len(self.sample_entries) - 1,
                ),
                (self.another_entry.channel_id, 1, 1),
            ],
        )
