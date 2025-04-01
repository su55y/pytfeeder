import unittest


from pytfeeder import config
from pytfeeder.defaults import default_data_path
from pytfeeder.rofi import ConfigRofi
from pytfeeder.tui import ConfigTUI


class TestConfig(unittest.TestCase):
    def test_default_data_paths(self):
        c = config.Config()
        data_path = default_data_path()
        self.assertEqual(c.log_file, data_path / config.LOGS_FILENAME)
        self.assertEqual(c.storage_path, data_path / config.STORAGE_FILENAME)

    def test_updating_tui_config(self):
        c = ConfigTUI()
        d = {
            "alphabetic_sort": True,
            "channel_feed_limit": 20,
            "channels_fmt": "new fmt",
        }

        for k, v in d.items():
            self.assertNotEqual(getattr(c, k), v)

        c.update(d)
        for k, v in d.items():
            self.assertEqual(getattr(c, k), v)

    def test_updating_rofi_config(self):
        c = ConfigRofi()
        d = {
            "alphabetic_sort": True,
            "channel_feed_limit": 20,
            "channels_fmt": "new fmt",
        }

        for k, v in d.items():
            self.assertNotEqual(getattr(c, k), v)

        c.update(d)
        for k, v in d.items():
            self.assertEqual(getattr(c, k), v)
