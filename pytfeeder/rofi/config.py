from dataclasses import dataclass
from typing import Any, Dict

from . import consts


@dataclass
class ConfigRofi:
    alphabetic_sort: bool = False
    channel_feed_limit: int = -1
    channels_fmt: str = consts.DEFAULT_CHANNELS_FMT
    datetime_fmt: str = consts.DEFAULT_DATETIME_FMT
    entries_fmt: str = consts.DEFAULT_ENTRIES_FMT
    feed_limit: int = -1
    offset: int = consts.DEFAULT_OFFSET
    separator: str = consts.DEFAULT_SEPARATOR
    unwatched_first: bool = False

    def update(self, kwargs: Dict[str, Any]) -> None:
        for k, v in kwargs.items():
            if k in vars(self).keys() and v:
                setattr(self, k, v)

    def __repr__(self) -> str:
        repr_str = "rofi:\n"
        repr_str += f"  alphabetic_sort: {self.alphabetic_sort}\n"
        repr_str += f"  channel_feed_limit: {self.channel_feed_limit}\n"
        repr_str += f"  channels_fmt: {self.channels_fmt}\n"
        repr_str += f"  datetime_fmt: {self.datetime_fmt}\n"
        repr_str += f"  entries_fmt: {self.entries_fmt}\n"
        repr_str += f"  feed_limit: {self.feed_limit}\n"
        repr_str += f"  offset: {self.offset}\n"
        repr_str += f"  separator: {self.separator}\n"

        return repr_str
