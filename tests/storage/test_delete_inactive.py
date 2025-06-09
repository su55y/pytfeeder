from pathlib import Path
import unittest

from pytfeeder import Storage
from pytfeeder.models import Channel
from .. import mocks, utils


class DeleteInactiveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        utils.setup_logging(filename=f"{Path(__file__).name}.log")
        cls.db_file = utils.temp_storage_path()
        cls.stor = Storage(cls.db_file)

    @classmethod
    def tearDownClass(cls):
        if cls.db_file.exists():
            cls.db_file.unlink()

    def test_delete_inactive(self):
        entries = mocks.sample_entries + mocks.another_sample_entries
        self.assertEqual(self.stor.add_entries(entries), len(entries))
        self.assertEqual(self.stor.select_entries_count(), len(entries))
        active_channels = [
            Channel(title=e.channel_id, channel_id=e.channel_id)
            for e in mocks.sample_entries
        ]
        self.stor.delete_inactive_channels(active_channels=active_channels)
        self.assertEqual(self.stor.select_entries_count(), len(mocks.sample_entries))
        self.assertEqual(self.stor.select_entries(), mocks.sample_entries)
