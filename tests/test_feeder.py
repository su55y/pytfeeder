from pathlib import Path
import unittest

from pytfeeder.config import Config
from pytfeeder.feeder import Feeder
from pytfeeder.storage import Storage
from . import mocks


class FeederTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_file = Path("/tmp/test_storage.db")
        if cls.db_file.exists():
            cls.db_file.unlink()
        cls.stor = Storage(cls.db_file)
        cls.config = Config(channels=[mocks.sample_channel], storage_path=cls.db_file)
        cls.feeder = Feeder(config=cls.config, storage=cls.stor)

    @classmethod
    def tearDownClass(cls):
        if cls.db_file.exists():
            cls.db_file.unlink()

    def test_refresh_channels(self):
        _ = self.stor.add_entries(mocks.sample_entries)
        before = self.feeder.channels[0].have_updates
        self.feeder.mark_as_watched(channel_id=mocks.sample_channel.channel_id)
        self.feeder.refresh_channels_stats()
        after = self.feeder.channels[0].have_updates
        self.assertNotEqual(before, after)
