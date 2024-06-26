from pathlib import Path
import unittest
from pytfeeder.config import Config
from pytfeeder.consts import DEFAULT_CHANNEL_FMT, DEFAULT_ENTRY_FMT, DEFAULT_LOG_FMT


class TestConfig(unittest.TestCase):
    def test_default_config(self):
        default_config = Config()
        config = Config(
            cache_dir=Path.home().joinpath(".cache/pytfeeder"),
            channels=list(),
            channels_fmt=DEFAULT_CHANNEL_FMT,
            channel_feed_limit=None,
            entries_fmt=DEFAULT_ENTRY_FMT,
            feed_limit=None,
            log_level=0,
            log_fmt=DEFAULT_LOG_FMT,
            unviewed_first=False,
        )
        self.assertEqual(default_config.channels, config.channels)
        self.assertEqual(default_config.channel_feed_limit, config.channel_feed_limit)
        self.assertEqual(default_config.feed_limit, config.feed_limit)
        self.assertEqual(default_config.log_level, config.log_level)
        self.assertEqual(default_config.log_file, config.log_file)
        self.assertEqual(default_config.log_fmt, config.log_fmt)
        self.assertEqual(default_config.storage_path, config.storage_path)
        self.assertEqual(default_config.unviewed_first, config.unviewed_first)
