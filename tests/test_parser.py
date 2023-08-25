import unittest

from pytfeeder.parser import YTFeedParser
from .mocks import raw_feed, sample_entries


class ParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = YTFeedParser(raw_feed)

    def test_parser(self):
        self.assertEqual(self.parser.entries, sample_entries)
