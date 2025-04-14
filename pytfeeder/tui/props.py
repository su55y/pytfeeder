import asyncio
import datetime as dt
from enum import Enum, auto
import time

from pytfeeder import Feeder, __version__  # FIXME: circular import
from pytfeeder.models import Channel, Entry
from .args import format_keybindings
from .consts import DEFAULT_KEYBINDS


class PageState(Enum):
    CHANNELS = auto()
    ENTRIES = auto()


class TuiProps:
    def __init__(self, feeder: Feeder) -> None:
        self.feeder = feeder
        self.c = self.feeder.config.tui
        if self.c.alphabetic_sort:
            self.feeder.config.channels.sort(key=lambda c_: c_.title.lower())
        self.channels: list[Channel] = list()
        self._set_channels()
        self.channel_indexes_map = {
            c.channel_id: i for i, c in enumerate(self.channels)
        }
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
        self._status_msg_creation_time = 0.0
        self._status_msg_text = ""
        self.unwatched_method = lambda _: 0
        if "{unwatched_count}" in self.c.channels_fmt:
            self.unwatched_method = lambda c_id: self.feeder.unwatched_count(c_id)
        if self.is_update_needed:
            self.initial_update()
        self.refresh_last_update()
        self.is_channels_outdated = False

    def feed(self) -> list[Entry]:
        return self.feeder.feed(
            limit=self.c.feed_limit, unwatched_first=self.c.unwatched_first
        )

    def channel_feed(self, channel_id: str) -> list[Entry]:
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

    def initial_update(self) -> None:
        print("updating...")
        new, err = asyncio.run(self.feeder.sync_entries())
        if err:
            self.status_msg = f"Error: {err}"
            return
        if new > 0:
            self.status_msg = f"{new} new entries"
            self.update_channels()
        else:
            self.status_msg = "no updates"

    @property
    def is_update_needed(self) -> bool:
        return not self.c.no_update and (
            self.c.always_update or self.is_update_interval_expired()
        )

    def is_update_interval_expired(self) -> bool:
        if not self.feeder.config.lock_file.exists():
            return True

        last_update = dt.datetime.fromtimestamp(
            float(self.feeder.config.lock_file.read_text())
        )
        if last_update < (
            dt.datetime.now() - dt.timedelta(minutes=self.c.update_interval)
        ):
            return True

        return False

    @property
    def statusbar_height(self) -> int:
        return 1 ^ self.c.hide_statusbar

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
        self.feeder.refresh_channels()
        self.is_channels_outdated = False
        self._set_channels()

    def _set_channels(self) -> None:
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
        except Exception as e:
            self.status_msg = f"refresh_last_update error: {e!r}"
        else:
            self.status_last_update = dt_str.strftime(self.c.last_update_fmt)

    def get_parent_channel_id(self) -> str | None:
        raise NotImplementedError("")

    def reload_lines(self, channel_id: str | None = None) -> None:
        raise NotImplementedError("")

    async def sync_and_reload(self) -> None:
        channel_id = self.get_parent_channel_id()
        new, err = await self.feeder.sync_entries()
        if err:
            self.status_msg = f"Error: {err}"
            return
        if new > 0:
            self.update_channels()
            self.reload_lines(channel_id)
            self.status_msg = f"{new} new updates"
        else:
            self.status_msg = "no updates"

        self.refresh_last_update()
