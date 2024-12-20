import logging
from pathlib import Path
import unittest
from pytfeeder.config import Config
import pytfeeder.consts as c


class TestConfig(unittest.TestCase):
    def test_dc(self):
        dc = Config()
        self.assertEqual(dc.cache_dir, Path.home() / ".cache/pytfeeder")
        self.assertEqual(dc.log_fmt, c.DEFAULT_LOG_FMT)
        self.assertEqual(dc.log_level, logging.NOTSET)
        self.assertEqual(dc.rofi_channels_fmt, c.DEFAULT_ROFI_CHANNELS_FMT)
        self.assertEqual(dc.rofi_entries_fmt, c.DEFAULT_ROFI_ENTRIES_FMT)
        self.assertEqual(dc.unviewed_first, False)
