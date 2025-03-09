import unittest


from pytfeeder.rofi.config import ConfigRofi
from pytfeeder.tui import ConfigTUI


class TestConfig(unittest.TestCase):
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
