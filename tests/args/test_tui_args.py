import unittest

from pytfeeder.tui import args as tui_args
from pytfeeder.tui import ConfigTUI


class TestTuiArgs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = tui_args.create_parser()

    def test_update_booleans(self):
        # config: False, args: True
        c1 = ConfigTUI()
        self.assertFalse(c1.alphabetic_sort)
        a1 = vars(self.p.parse_args(args=["-A"]))
        as_value1 = a1.get("alphabetic_sort")
        self.assertIsNotNone(as_value1)
        self.assertTrue(as_value1)
        c1.update(a1)
        self.assertTrue(c1.alphabetic_sort)

        # config: True, args: False
        c2 = ConfigTUI(alphabetic_sort=True)
        self.assertTrue(c2.alphabetic_sort)
        a2 = vars(self.p.parse_args(args=[]))
        as_value2 = a2.get("alphabetic_sort")
        self.assertIsNotNone(as_value2)
        self.assertFalse(as_value2)
        c2.update(a2)
        self.assertTrue(c2.alphabetic_sort)

    def test_update_ints(self):
        c1 = ConfigTUI(channel_feed_limit=10, feed_limit=100)
        a1 = vars(self.p.parse_args(args=[]))
        self.assertIsNone(a1.get("feed_limit"))
        self.assertIsNone(a1.get("channel_feed_limit"))
        c1.update(a1)
        self.assertEqual(c1.channel_feed_limit, 10)
        self.assertEqual(c1.feed_limit, 100)

        a2 = vars(self.p.parse_args(args=["-l", "20", "-L", "200"]))
        c1.update(a2)
        self.assertEqual(c1.channel_feed_limit, 20)
        self.assertEqual(c1.feed_limit, 200)

    def test_update_new_mark(self):
        c = ConfigTUI(new_mark="|||")
        a = vars(self.p.parse_args(args=[]))
        c.update(a)
        self.assertEqual(c.new_mark, "|||")
