from dataclasses import dataclass
from typing import Any, Dict

from . import consts


@dataclass
class ConfigRofi:
    alphabetic_sort: bool = False
    channel_feed_limit: int = -1
    channels_fmt: str = consts.DEFAULT_CHANNELS_FMT
    feed_entries_fmt: str = consts.DEFAULT_ENTRIES_FMT
    datetime_fmt: str = consts.DEFAULT_DATETIME_FMT
    entries_fmt: str = consts.DEFAULT_ENTRIES_FMT
    feed_limit: int = -1
    separator: str = consts.DEFAULT_SEPARATOR
    unwatched_first: bool = False

    def update(self, kwargs: Dict[str, Any]) -> None:
        for k, v in kwargs.items():
            if k in vars(self).keys() and v:
                setattr(self, k, v)

    def __repr__(self) -> str:
        repr_str = "rofi:\n"
        for k, v in sorted(vars(self).items()):
            repr_str += f"  {k}: {v!r}\n"
        return repr_str
