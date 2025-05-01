from dataclasses import dataclass
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


@dataclass
class Line:
    data: Channel | Entry
    is_active: bool = False


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
        self.lines = list(map(Line, self.channels))
        self.max_len_chan_title = max(len(c.title) for c in self.channels)
        self.new_marks = {0: " " * len(self.c.new_mark), 1: self.c.new_mark}
        self.page_state = PageState.CHANNELS
        self.status_last_update = ""
        self.status_msg_lifetime = 3
        self._status_msg_creation_time = 0.0
        self._status_msg_text = ""
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

    def find_channel_index_by_id(self, channel_id: str) -> int:
        i = self.channel_indexes_map.get(channel_id)
        if i is None:
            raise Exception(
                f"Unknown {channel_id = !r}\nin {self.channel_indexes_map.keys() = !r}"
            )
        return i

    def get_lines_by_id(self, channel_id: str) -> list[Line]:
        if channel_id == "feed":
            self._is_feed_opened = True
            return list(map(Line, self.feed()))
        self._is_feed_opened = False
        return list(map(Line, self.channel_feed(channel_id)))

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

    def handle_move(self, parent_index: int, gravity: int) -> int | None:
        if (
            self.page_state != PageState.ENTRIES
            or self.is_filtered
            or len(self.channels) < 2
            or parent_index not in range(len(self.channels))
            or abs(gravity) != 1
        ):
            return None

        new_parent_index = (parent_index + gravity) % len(self.channels)
        for i in range(1, len(self.channels)):
            if self.channels[new_parent_index].entries_count > 0:
                break
            next_candidate = parent_index + (i * gravity)
            new_parent_index = (next_candidate + gravity) % len(self.channels)
        else:
            return None

        if new_parent_index == parent_index:
            return None
        self.lines = self.get_lines_by_id(self.channels[new_parent_index].channel_id)
        self.index = 0
        return new_parent_index

    def mark_as_deleted(self) -> bool:
        if len(self.lines) == 0:
            return False
        selected_data = self.lines[self.index].data
        if self.page_state != PageState.ENTRIES or not isinstance(selected_data, Entry):
            return False
        if not self.feeder.mark_entry_as_deleted(selected_data.id):
            self.status_msg = "Something went wrong"
            return False
        self.is_channels_outdated = True
        del self.lines[self.index]
        self.index = max(0, self.index - 1)
        return True

    def mark_as_watched(self) -> None:
        selected_data = self.lines[self.index].data
        if self.page_state == PageState.CHANNELS:
            if not isinstance(selected_data, Channel):
                raise Exception(f"Unexpected channel type {type(selected_data)!r}")
            if selected_data.channel_id == "feed":
                return
            unwatched = not selected_data.have_updates
            self.feeder.mark_as_watched(
                channel_id=selected_data.channel_id, unwatched=unwatched
            )
            self.update_channels()
            if not self.c.hide_feed:
                self.reload_lines()
        elif self.page_state == PageState.ENTRIES:
            if not isinstance(selected_data, Entry):
                raise Exception(f"Unexpected entry type {type(selected_data)!r}")
            unwatched = selected_data.is_viewed
            self.feeder.mark_as_watched(id=selected_data.id, unwatched=unwatched)
            self.is_channels_outdated = True
            selected_data.is_viewed = not unwatched
            self.index = (self.index + 1) % len(self.lines)

    def mark_as_watched_all(self, parent_index: int = -1) -> None:
        selected_data = self.lines[self.index].data
        if self.page_state == PageState.CHANNELS and isinstance(selected_data, Channel):
            self.feeder.mark_as_watched(
                unwatched=all(not c.have_updates for c in self.feeder.channels)
            )
            self.update_channels()
            if not self.c.hide_feed:
                self.reload_lines()
        elif self.page_state == PageState.ENTRIES and isinstance(selected_data, Entry):
            if self.channels[parent_index].channel_id == "feed":
                unwatched = all(not c.have_updates for c in self.channels)
                self.feeder.mark_as_watched(unwatched=unwatched)
                self.is_channels_outdated = True
                for i in range(len(self.channels)):
                    self.channels[i].have_updates = unwatched
                for i in range(len(self.lines)):
                    self.lines[i].data.is_viewed = not unwatched  # type: ignore
            else:
                unwatched = not self.channels[parent_index].have_updates
                self.feeder.mark_as_watched(
                    channel_id=selected_data.channel_id, unwatched=unwatched
                )
                self.is_channels_outdated = True
                self.channels[parent_index].have_updates = unwatched
                for i in range(len(self.lines)):
                    self.lines[i].data.is_viewed = not unwatched  # type: ignore

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
            unwatched_count = self.feeder.unwatched_count("feed")
            feed_channel = Channel(
                title="Feed",
                channel_id="feed",
                entries_count=self.feeder.total_entries_count(),
                have_updates=bool(unwatched_count),
                unwatched_count=unwatched_count,
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
        if self.page_state == PageState.CHANNELS:
            self.lines = list(map(Line, self.channels))
        elif self.page_state == PageState.ENTRIES and channel_id:
            self.index = 0
            self.lines = self.get_lines_by_id(channel_id)

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
