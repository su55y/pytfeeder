from pathlib import Path
import unittest

from pytfeeder import Config, Feeder, Storage
from pytfeeder.models import Channel
from .. import mocks, utils


class IncludeUnknownTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        utils.setup_logging(filename=f"{Path(__file__).name}.log")
        cls.db_file = Path("/tmp/test_storage.db")
        if cls.db_file.exists():
            cls.db_file.unlink()

    @classmethod
    def tearDownClass(cls):
        if cls.db_file.exists():
            cls.db_file.unlink()

    def test_feed_without_unknown(self):
        s = Storage(self.db_file)
        entry = mocks.sample_entries[0]
        channel = Channel(title="test", channel_id=entry.channel_id)
        self.assertEqual(s.add_entries([entry, mocks.another_sample_entries[0]]), 2)
        self.assertEqual(len(s.select_entries()), 2)
        self.assertEqual(len(s.select_entries(in_channels=[channel])), 1)
        c = Config(channels=[channel])
        f = Feeder(c, s)
        self.assertEqual(len(f.feed()), 1)
        self.assertEqual(len(f.feed(include_unknown=True)), 2)
