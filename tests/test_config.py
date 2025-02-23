import logging
from pathlib import Path
import unittest
from pytfeeder.config import Config
import pytfeeder.consts as c
from pytfeeder.tui import ConfigTUI


class TestConfig(unittest.TestCase):
    def test_default_config(self):
        dc = Config()
        self.assertEqual(dc.alphabetic_sort, False)
        self.assertEqual(dc.cache_dir, Path.home() / ".cache/pytfeeder")
        self.assertEqual(dc.datetime_fmt, c.DEFAULT_DATETIME_FMT)
        self.assertEqual(dc.log_fmt, c.DEFAULT_LOG_FMT)
        self.assertEqual(dc.log_level, logging.NOTSET)
        self.assertEqual(dc.rofi_channels_fmt, c.DEFAULT_ROFI_CHANNELS_FMT)
        self.assertEqual(dc.rofi_entries_fmt, c.DEFAULT_ROFI_ENTRIES_FMT)
        self.assertEqual(dc.unwatched_first, False)
        self.assertEqual(dc.tui, ConfigTUI())
