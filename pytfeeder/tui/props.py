from enum import Enum, auto
from typing import List

from pytfeeder.feeder import Feeder
from pytfeeder.models import Channel
from .args import format_keybindings


class PageState(Enum):
    CHANNELS = auto()
    ENTRIES = auto()


class TuiProps:
    def __init__(self) -> None:
        self.channels = list()
        self.help_lines = list(map(lambda s: s.lstrip(), format_keybindings()))
        self.page_state = PageState.CHANNELS
        self.index = 0
        self._status_msg = ""
        self._status_msg_time = 0
        self._last_update = ""

    def _set_channels(
        self,
        feeder: Feeder,
        hide_feed: bool = False,
        channels: List[Channel] = list(),
    ) -> None:
        if channels:
            feeder.channels = channels

        if feeder.config.alphabetic_sort:
            feeder.channels.sort(key=lambda c: c.title)

        if hide_feed:
            self.channels = feeder.channels
        else:
            feed_channel = Channel(
                title="Feed",
                channel_id="feed",
                have_updates=bool(feeder.unviewed_count()),
            )
            self.channels = [feed_channel, *feeder.channels]
