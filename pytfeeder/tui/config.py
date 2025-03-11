from dataclasses import dataclass
from typing import Any, Dict

from . import consts


@dataclass
class ConfigTUI:
    always_update: bool = False
    alphabetic_sort: bool = False
    channels_fmt: str = consts.DEFAULT_CHANNELS_FMT
    channel_feed_limit: int = -1
    datetime_fmt: str = consts.DEFAULT_DATETIME_FMT
    entries_fmt: str = consts.DEFAULT_ENTRIES_FMT
    feed_entries_fmt: str = consts.DEFAULT_FEED_ENTRIES_FMT
    feed_limit: int = -1
    hide_feed: bool = False
    last_update_fmt: str = consts.DEFAULT_LAST_UPDATE_FMT
    new_mark: str = consts.DEFAULT_NEW_MARK
    status_fmt: str = consts.DEFAULT_STATUS_FMT
    unwatched_first: bool = False
    update_interval: int = consts.DEFAULT_UPDATE_INTERVAL_MINS
    macro1: str = ""
    macro2: str = ""
    macro3: str = ""
    macro4: str = ""

    def update(self, kwargs: Dict[str, Any]) -> None:
        for k, v in kwargs.items():
            if k in vars(self).keys() and v:
                setattr(self, k, v)

    def __repr__(self) -> str:
        repr_str = "tui:\n"
        repr_str += f"  alphabetic_sort: {self.alphabetic_sort}\n"
        repr_str += f"  always_update: {self.always_update}\n"
        repr_str += f"  channel_feed_limit: {self.channel_feed_limit}\n"
        repr_str += f"  channels_fmt: {self.channels_fmt!r}\n"
        repr_str += f"  datetime_fmt: {self.datetime_fmt!r}\n"
        repr_str += f"  entries_fmt: {self.entries_fmt!r}\n"
        repr_str += f"  feed_entries_fmt: {self.feed_entries_fmt!r}\n"
        repr_str += f"  feed_limit: {self.feed_limit}\n"
        repr_str += f"  hide_feed: {self.hide_feed}\n"
        repr_str += f"  last_update_fmt: {self.last_update_fmt!r}\n"
        repr_str += f"  new_mark: {self.new_mark!r}\n"
        repr_str += f"  status_fmt: {self.status_fmt!r}\n"
        repr_str += f"  unwatched_first: {self.unwatched_first}\n"
        repr_str += f"  update_interval: {self.update_interval}\n"
        repr_str += f"  macro1: {self.macro1!r}\n"
        repr_str += f"  macro2: {self.macro2!r}\n"
        repr_str += f"  macro3: {self.macro3!r}\n"
        repr_str += f"  macro4: {self.macro4!r}\n"
        return repr_str
