import datetime as dt
from enum import Enum, auto
from pathlib import Path
from typing import List

from pytfeeder.feeder import Feeder
from pytfeeder.models import Channel
from .config import ConfigTUI
from .args import format_keybindings


class PageState(Enum):
    CHANNELS = auto()
    ENTRIES = auto()


class TuiProps:
    def __init__(self, tui_config: ConfigTUI) -> None:
        self.c = tui_config
        self.channels = list()
        self.entry_formats = [self.c.entries_fmt, self.c.feed_entries_fmt]
        self.help_lines = list(map(lambda s: s.lstrip(), format_keybindings()))
        self.page_state = PageState.CHANNELS
        self.index = 0
        self.new_marks = {0: " " * len(self.c.new_mark), 1: self.c.new_mark}
        self._status_msg = ""
        self._status_msg_lifetime = 0
        self._last_update = ""
        self._is_feed_opened = False
        self.unwatched_method = lambda _: 0

    @property
    def current_entry_format(self) -> str:
        return self.entry_formats[self._is_feed_opened]

    def _set_channels(self, feeder: Feeder, channels: List[Channel] = list()) -> None:
        if channels:
            feeder.channels = channels

        if feeder.config.alphabetic_sort:
            feeder.channels.sort(key=lambda c: c.title)

        if self.c.hide_feed:
            self.channels = feeder.channels
        else:
            feed_channel = Channel(
                title="Feed",
                channel_id="feed",
                have_updates=bool(feeder.unviewed_count()),
            )
            self.channels = [feed_channel, *feeder.channels]

    def refresh_last_update(self, lock_path: Path) -> None:
        try:
            dt_str = dt.datetime.fromtimestamp(float(lock_path.read_text()))
        except:
            pass
        else:
            self._last_update = dt_str.strftime(self.c.last_update_fmt)
