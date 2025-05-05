from pathlib import Path
import unittest

from pytfeeder import Feeder, Config, Storage
from pytfeeder.models import Channel
from pytfeeder.entry_points.run_pytfeeder_curses import App as CursesApp, Gravity
from pytfeeder.tui.props import PageState

from .. import mocks, utils


class TestNextPrev(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        utils.setup_logging(filename=f"{Path(__file__).name}.log")
        cls.db_file = Path("/tmp/test_storage.db")
        if cls.db_file.exists():
            cls.db_file.unlink()

    def setUp(self):
        c = Config(channels=list())
        c.tui.alphabetic_sort = True
        c.tui.hide_feed = True
        c.tui.no_update = True
        c.tui.status_fmt = "{title}"
        s = Storage(self.db_file)
        self.f = Feeder(c, s)

    def tearDown(self):
        del self.f
        if self.db_file.exists():
            self.db_file.unlink()

    def test_handle_move_next_prev(self):
        """Jump over empty on next"""

        sample_channels = [
            Channel(
                title="a",
                channel_id=mocks.sample_entries[0].channel_id,
            ),
            Channel(title="b", channel_id="b" * 24),
            Channel(
                title="c",
                channel_id=mocks.another_sample_entries[0].channel_id,
            ),
        ]
        self.f.stor.add_entries(
            mocks.sample_entries + [mocks.another_sample_entries[0]]
        )
        self.f.config.channels = sample_channels.copy()

        app = CursesApp(self.f)
        self.assertEqual(len(app.channels), len(sample_channels))

        app.move_right()
        self.assertEqual(app.page_state, PageState.ENTRIES)
        self.assertEqual(app.parent_index, 0)
        self.assertEqual(app.status, sample_channels[0].title)

        self.assertTrue(app.handle_move_next_prev(Gravity.DOWN))
        self.assertEqual(app.parent_index, 2)
        self.assertEqual(app.status, sample_channels[2].title)

    def test_handle_move_next_prev2(self):
        """Jump over empty on prev"""

        sample_channels = [
            Channel(
                title="a",
                channel_id=mocks.sample_entries[0].channel_id,
            ),
            Channel(title="b", channel_id="b" * 24),
            Channel(
                title="c",
                channel_id=mocks.another_sample_entries[0].channel_id,
            ),
        ]
        self.f.stor.add_entries(
            mocks.sample_entries + [mocks.another_sample_entries[0]]
        )
        self.f.config.channels = sample_channels.copy()

        app = CursesApp(self.f)
        self.assertEqual(len(app.channels), len(sample_channels))

        app.move_down()
        app.move_down()
        app.move_right()
        self.assertEqual(app.page_state, PageState.ENTRIES)
        self.assertEqual(app.parent_index, 2)
        self.assertEqual(app.status, sample_channels[2].title)

        self.assertTrue(app.handle_move_next_prev(Gravity.UP))
        self.assertEqual(app.parent_index, 0)
        self.assertEqual(app.status, sample_channels[0].title)

    def test_handle_move_next_prev3(self):
        """Two channels, second are empty"""

        sample_channels = [
            Channel(
                title="a",
                channel_id=mocks.sample_entries[0].channel_id,
            ),
            Channel(title="b", channel_id="b" * 24),
        ]

        self.f.config.channels = sample_channels.copy()
        self.f.stor.add_entries(mocks.sample_entries)
        app = CursesApp(self.f)
        self.assertEqual(len(app.channels), len(sample_channels))

        app.move_right()
        self.assertEqual(app.page_state, PageState.ENTRIES)
        self.assertEqual(app.parent_index, 0)
        self.assertEqual(app.status, sample_channels[0].title)

        self.assertFalse(app.handle_move_next_prev(Gravity.DOWN))
        self.assertEqual(app.parent_index, 0)
        self.assertEqual(app.status, sample_channels[0].title)

        self.assertFalse(app.handle_move_next_prev(Gravity.UP))
        self.assertEqual(app.parent_index, 0)
        self.assertEqual(app.status, sample_channels[0].title)
