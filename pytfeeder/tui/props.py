import datetime as dt
from enum import Enum, auto
import time
from typing import List

from pytfeeder.feeder import Feeder
from pytfeeder.models import Channel, Entry
from pytfeeder import __version__
from .args import format_keybindings
from .consts import DEFAULT_KEYBINDS


class PageState(Enum):
    CHANNELS = auto()
    ENTRIES = auto()


class TuiProps:
    def __init__(self, feeder: Feeder) -> None:
        self.feeder = feeder
        self.c = self.feeder.config.tui
        self.channels = list()
        self._set_channels()
        self.entry_formats = [self.c.entries_fmt, self.c.feed_entries_fmt]
        self.help_status = " version {version} [h,q,Left]: close help".format(
            version=__version__
        )
        self.help_lines = list(map(lambda s: s.lstrip(), format_keybindings()))
        self.index = 0
        self.is_filtered = False
        self._is_feed_opened = False
        self.max_len_chan_title = max(len(c.title) for c in self.channels)
        self.new_marks = {0: " " * len(self.c.new_mark), 1: self.c.new_mark}
        self.page_state = PageState.CHANNELS
        self.status_last_update = ""
        self.status_msg_lifetime = 3
        self._status_msg_creation_time = 0
        self._status_msg_text = ""
        self.unwatched_method = lambda _: 0
        if "{unwatched_count}" in self.c.channels_fmt:
            self.unwatched_method = lambda c_id: self.feeder.unwatched_count(c_id)

    def feed(self) -> List[Entry]:
        return self.feeder.feed(
            limit=self.c.feed_limit, unwatched_first=self.c.unwatched_first
        )

    def channel_feed(self, channel_id: str) -> List[Entry]:
        return self.feeder.channel_feed(
            channel_id=channel_id,
            limit=self.c.channel_feed_limit,
            unwatched_first=self.c.unwatched_first,
        )

    def channel_title(self, channel_id: str) -> str:
        return f"{self.feeder.channel_title(channel_id):^{self.max_len_chan_title}s}"

    @property
    def current_entry_format(self) -> str:
        return self.entry_formats[self._is_feed_opened]

    def status_index(self, lines_count: int) -> str:
        num_fmt = f"%{len(str(lines_count))}d"
        index = self.index + 1
        if self.is_filtered and lines_count == 0:
            index = 0
        return "[%s/%s]" % ((num_fmt % index), (num_fmt % lines_count))

    @property
    def status_keybinds(self) -> str:
        if self.is_filtered:
            return f"[h]: cancel filter, {DEFAULT_KEYBINDS}"
        return DEFAULT_KEYBINDS

    @property
    def status_msg(self) -> str:
        if (
            self._status_msg_text
            and (time.perf_counter() - self._status_msg_creation_time)
            > self.status_msg_lifetime
        ):
            self._status_msg_text = ""
        return self._status_msg_text

    @status_msg.setter
    def status_msg(self, text: str) -> None:
        self._status_msg_text = text
        self._status_msg_creation_time = time.perf_counter()

    def update_channels(self) -> None:
        self._set_channels(self.feeder.update_channels())

    def _set_channels(self, channels: List[Channel] = list()) -> None:
        if channels:
            self.feeder.channels = channels

        if self.c.alphabetic_sort:
            self.feeder.channels.sort(key=lambda c: c.title)

        if self.c.hide_feed:
            self.channels = self.feeder.channels
        else:
            feed_channel = Channel(
                title="Feed",
                channel_id="feed",
                have_updates=bool(self.feeder.unwatched_count()),
            )
            self.channels = [feed_channel, *self.feeder.channels]

    def refresh_last_update(self) -> None:
        try:
            dt_str = dt.datetime.fromtimestamp(
                float(self.feeder.config.lock_file.read_text())
            )
        except:
            pass
        else:
            self.status_last_update = dt_str.strftime(self.c.last_update_fmt)
