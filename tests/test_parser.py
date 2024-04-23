import unittest

from pytfeeder.parser import YTFeedParser
from . import mocks


class ParserTest(unittest.TestCase):
    def test_parser(self):
        parser = YTFeedParser(mocks.raw_feed)
        self.assertEqual(parser.entries, mocks.sample_entries)
