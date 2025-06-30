from dataclasses import dataclass
import asyncio
import datetime as dt
from enum import Enum, auto
import time
import sys
from typing import Callable

from pytfeeder import Feeder, __version__, utils  # FIXME: circular import
from pytfeeder.models import Channel, Entry, Tag
from .args import format_keybindings
from .consts import DEFAULT_KEYBINDS


class PageState(Enum):
    CHANNELS = auto()
    ENTRIES = auto()
    RESTORING = auto()
    RESTORING_ENTRIES = auto()
    TAGS = auto()
    TAGS_CHANNELS = auto()


@dataclass
class Line:
    data: Channel | Entry | Tag
    is_active: bool = False


class TuiProps:
    def __init__(self, feeder: Feeder) -> None:
        self.feeder = feeder
        self.c = self.feeder.config.tui
        if self.c.alphabetic_sort:
            self.feeder.channels_aplhabetic_sort()
        self.channels: list[Channel] = list()
        self.__max_unwatched_num_len = 0
        self.__max_total_num_len = 0
        self._set_channels()
        self._channels_indexes_map = self._make_channels_indexes_map()
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
        self.parent_index = -1
        self.status_last_update = ""
        self.status_msg_lifetime = 3
        self._status_msg_creation_time = 0.0
        self._status_msg_text = ""
        if self.is_update_needed:
            self.initial_update()
        self.refresh_last_update()
        self.is_channels_outdated = False
        self.__is_download_allowed = False
        self.__is_notify_allowed = False
        self.__is_play_allowed = False
        self.__is_executables_checked = False
        self._last_selected_tag_title = ""

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
        i = self._channels_indexes_map.get(channel_id)
        if i is None:
            raise Exception(f"{channel_id = !r} not found")
        return i

    def move_prev_unwatched(self) -> None:
        if self.page_state != PageState.ENTRIES or len(self.lines) < 2:
            return

        for i in range(self.index - 1, self.index - len(self.lines), -1):
            i = i % len(self.lines)
            if not self.lines[i].data.is_viewed:  # type: ignore
                self.index = i
                return

    def move_next_unwatched(self) -> None:
        if self.page_state != PageState.ENTRIES or len(self.lines) < 2:
            return

        for i in range(self.index + 1, self.index + len(self.lines)):
            i = i % len(self.lines)
            if not self.lines[i].data.is_viewed:  # type: ignore
                self.index = i
                return

    def format_unwatched_total_key(self, c: Channel | Tag) -> str:
        w = self.__max_unwatched_num_len + self.__max_total_num_len + 3
        s = f"({c.unwatched_count}/{c.entries_count})"
        return f"{s:>{w}}"

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
        last_update = self.feeder.last_update
        if last_update is None:
            return True
        return last_update < (
            dt.datetime.now() - dt.timedelta(minutes=self.c.update_interval)
        )

    def handle_move(self, gravity: int) -> bool:
        if (
            self.page_state != PageState.ENTRIES
            or self.is_filtered
            or len(self.channels) < 2
            or self.parent_index not in range(len(self.channels))
            or abs(gravity) != 1
        ):
            return False

        new_parent_index = (self.parent_index + gravity) % len(self.channels)
        for i in range(1, len(self.channels)):
            if self.channels[new_parent_index].entries_count > 0:
                break
            next_candidate = self.parent_index + (i * gravity)
            new_parent_index = (next_candidate + gravity) % len(self.channels)
        else:
            return False

        if new_parent_index == self.parent_index:
            return False

        self.lines = self.get_lines_by_id(self.channels[new_parent_index].channel_id)
        self.parent_index = new_parent_index
        self.index = 0
        return True

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
        self.lines = self.get_lines_by_id(self.channels[self.parent_index].channel_id)
        self.index = max(0, min(self.index, len(self.lines) - 1))
        return True

    def mark_all_as_deleted(self) -> bool:
        channel_id = self.channels[self.parent_index].channel_id
        if channel_id == "feed":
            return False
        c = self.feeder.mark_channel_as_deleted(channel_id)
        if c <= 0:
            self.status_msg = "Something went wrong"
            return False
        self.status_msg = f"{c} entries were deleted"
        self.update_channels()
        self.parent_index = min(self.parent_index, len(self.channels) - 1)
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

    def mark_as_watched_all(self) -> None:
        selected_data = self.lines[self.index].data
        if self.page_state == PageState.CHANNELS and isinstance(selected_data, Channel):
            self.feeder.mark_as_watched(
                unwatched=all(not c.have_updates for c in self.feeder.channels)
            )
            self.update_channels()
            if not self.c.hide_feed:
                self.reload_lines()
        elif self.page_state == PageState.ENTRIES and isinstance(selected_data, Entry):
            if self.is_channels_outdated:
                self.update_channels()
            if self.channels[self.parent_index].channel_id == "feed":
                unwatched = all(not c.have_updates for c in self.channels)
                self.feeder.mark_as_watched(unwatched=unwatched)
                self.is_channels_outdated = True
                for i in range(len(self.channels)):
                    self.channels[i].have_updates = unwatched
                for i in range(len(self.lines)):
                    self.lines[i].data.is_viewed = not unwatched  # type: ignore
            else:
                unwatched = not self.channels[self.parent_index].have_updates
                self.feeder.mark_as_watched(
                    channel_id=selected_data.channel_id, unwatched=unwatched
                )
                self.is_channels_outdated = True
                self.channels[self.parent_index].have_updates = unwatched
                for i in range(len(self.lines)):
                    self.lines[i].data.is_viewed = not unwatched  # type: ignore

    def _reset_filter(self) -> None:
        self.is_filtered = False
        self.index = 0
        if self.page_state == PageState.CHANNELS:
            self.lines = list(map(Line, self.channels))
        elif self.page_state == PageState.ENTRIES:
            selected_data = self.channels[self.parent_index]
            self.lines = self.get_lines_by_id(selected_data.channel_id)

    def restore_channel(self, c: Channel) -> bool:
        if self.page_state != PageState.RESTORING:
            return False
        count = self.feeder.restore_channel(c)
        if count == 0:
            return False
        self.is_channels_outdated = True
        self.status_msg = f"{count} entries was restored"
        return True

    def enter_restore(self) -> bool:
        if self.page_state == PageState.RESTORING or self.is_filtered:
            return False

        channels = self.feeder.channels_with_deleted()
        if len(channels) == 0:
            self.status_msg = "No deleted"
            return False

        self.lines = list(map(Line, channels))
        self.index = max(0, min(self.index, len(self.lines) - 1))
        self.page_state = PageState.RESTORING
        return True

    def enter_restore_entries(self) -> bool:
        if len(self.lines) == 0 or self.page_state != PageState.RESTORING:
            return False
        selected_data = self.lines[self.index].data
        if not isinstance(selected_data, Channel):
            self.status_msg = f"Unexpected channel type {type(selected_data)}"
            return False
        entries = self.feeder.channels_deleted_entries(selected_data.channel_id)
        if len(entries) == 0:
            self.status_msg = f"{selected_data.title!r} don't have deleted entries"
            return False
        self.lines = list(map(Line, entries))
        self.index = 0
        self.page_state = PageState.RESTORING_ENTRIES
        return True

    def toggle_is_deleted(self, entry: Entry) -> None:
        if self.feeder.toggle_is_deleted(entry.id):
            entry.is_deleted = not entry.is_deleted
            self.index = max(0, min(self.index + 1, len(self.lines) - 1))
            self.is_channels_outdated = True

    def show_tags(self) -> bool:
        if self.is_channels_outdated:
            self.update_channels()
        if len(self.feeder.tags_map) == 0:
            self.status_msg = "No tags"
            return False
        self.index = 0
        self.lines = list(map(Line, self.feeder.tags_map.values()))
        self.page_state = PageState.TAGS
        return True

    def select_tag(self, tag: Tag) -> None:
        self.lines = list(map(Line, tag.channels))
        self.index = 0
        self.page_state = PageState.TAGS_CHANNELS
        self._last_selected_tag_title = tag.title

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

    def _make_channels_indexes_map(self) -> dict[str, int]:
        return {c.channel_id: i for i, c in enumerate(self.channels)}

    def update_channels(self) -> None:
        self.feeder.refresh_channels_stats()
        self.is_channels_outdated = False
        self._set_channels()
        self._channels_indexes_map = self._make_channels_indexes_map()

    def _set_channels(self) -> None:
        if self.c.hide_feed:
            self.channels = self.feeder.channels
            self.__max_unwatched_num_len = max(
                len(str(c.unwatched_count)) for c in self.channels
            )
            self.__max_total_num_len = max(
                len(str(c.entries_count)) for c in self.channels
            )
        else:
            unwatched_count = self.feeder.unwatched_count()
            total_entries_count = self.feeder.total_entries_count(exclude_hidden=True)
            self.__max_unwatched_num_len = len(str(unwatched_count))
            self.__max_total_num_len = len(str(total_entries_count))
            feed_channel = Channel(
                title="Feed",
                channel_id="feed",
                entries_count=total_entries_count,
                have_updates=bool(unwatched_count),
                unwatched_count=unwatched_count,
            )
            self.channels = [feed_channel, *self.feeder.channels]

        if self.c.hide_empty and len(self.channels) > 1:
            self.channels = [c for c in self.channels if c.entries_count > 0]
            if len(self.channels) == 0:
                print("All channels are empty")
                sys.exit(0)
        if self.c.unwatched_first:
            self.channels.sort(key=lambda c: not c.have_updates)

    def refresh_last_update(self) -> None:
        last_update = self.feeder.last_update
        if last_update is None:
            self.status_last_update = "Unknown"
        else:
            self.status_last_update = last_update.strftime(self.c.last_update_fmt)

    def reload_lines(self, channel_id: str | None = None) -> None:
        if self.page_state == PageState.CHANNELS:
            self.lines = list(map(Line, self.channels))
        elif self.page_state == PageState.ENTRIES and channel_id:
            self.index = 0
            self.lines = self.get_lines_by_id(channel_id)

    def toggle_unwathced_first(self) -> None:
        if self.is_filtered:
            return
        self.c.unwatched_first = not self.c.unwatched_first
        index = self.index
        if self.page_state == PageState.ENTRIES:
            index = self.parent_index
        current_channel_id = self.channels[index].channel_id

        self.update_channels()

        if self.page_state == PageState.ENTRIES:
            self.parent_index = self.find_channel_index_by_id(current_channel_id)
            self.reload_lines(current_channel_id)
        elif self.page_state == PageState.CHANNELS:
            self.index = self.find_channel_index_by_id(current_channel_id)
            self.reload_lines()

    async def sync_and_reload(self) -> None:
        channel_id = None
        if self.page_state == PageState.ENTRIES:
            channel_id = self.channels[self.parent_index].channel_id

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

    def toggle_empty_channels_visability(self) -> None:
        if self.page_state != PageState.CHANNELS or self.is_filtered:
            return
        self.c.hide_empty = not self.c.hide_empty
        self._set_channels()
        self.reload_lines()
        self.index = min(self.index, len(self.lines) - 1)

    def _check_executables(self) -> None:
        if self.__is_executables_checked:
            return

        from shutil import which

        self.__is_download_allowed = bool(which("tsp") and which("yt-dlp"))
        self.__is_play_allowed = bool(which("setsid") and which("mpv"))
        self.__is_notify_allowed = bool(which("notify-send"))
        self.__is_executables_checked = True

    def download(self) -> None:
        self._check_executables()
        if not self.__is_download_allowed:
            self.status_msg = "Download not allowed (tsp or yt-dlp not found)"
            return

        if len(self.lines) == 0 or self.page_state != PageState.ENTRIES:
            return
        selected_data = self.lines[self.index].data
        if not isinstance(selected_data, Entry):
            raise Exception(f"Unexpected entry type {type(selected_data)!r}")

        utils.download_video(
            entry=selected_data,
            output=self.c.download_output,
            send_notification=self.__is_notify_allowed,
        )
        if not selected_data.is_viewed:
            self.mark_as_watched()

    def download_all(self, callback: Callable[[int], bool] | None = None) -> None:
        self._check_executables()
        if not self.__is_download_allowed:
            self.status_msg = "Download not allowed (tsp or yt-dlp not found)"
            return

        if len(self.lines) == 0:
            return
        selected_data = self.lines[self.index].data
        if self.page_state != PageState.ENTRIES or not isinstance(selected_data, Entry):
            return

        entries = [l.data for l in self.lines if l.data.is_viewed is False]  # type: ignore
        if len(entries) == 0:
            return

        if callback and not callback(len(entries)):
            return

        utils.download_all(
            entries=entries,  # type: ignore
            output=self.c.download_output,
            send_notification=self.__is_notify_allowed,
        )
        self.mark_as_watched_all()

    def play(self, entry: Entry) -> None:
        self._check_executables()
        if not self.__is_play_allowed:
            self.status_msg = "Play not allowed (setsid or mpv not found)"
            return
        utils.play_video(entry, self.__is_notify_allowed)
