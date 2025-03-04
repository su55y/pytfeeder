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

    def parse_config_file(self, kw: Dict[str, Any]) -> None:
        if alphabetic_sort := kw.get("alphabetic_sort"):
            self.alphabetic_sort = bool(alphabetic_sort)
        if channel_feed_limit := kw.get("channel_feed_limit"):
            self.channel_feed_limit = channel_feed_limit
        if channels_fmt := kw.get("channels_fmt"):
            self.channels_fmt = channels_fmt
        if datetime_fmt := kw.get("datetime_fmt"):
            self.datetime_fmt = datetime_fmt
        if entries_fmt := kw.get("entries_fmt"):
            self.entries_fmt = entries_fmt
        if feed_limit := kw.get("feed_limit"):
            self.feed_limit = feed_limit
        if separator := kw.get("separator"):
            self.separator = separator

    def parse_args(self, kw: Dict[str, Any]) -> None:
        if alphabetic_sort := kw.get("alphabetic_sort"):
            self.alphabetic_sort = alphabetic_sort
        if channel_feed_limit := kw.get("channel_feed_limit"):
            self.channel_feed_limit = channel_feed_limit
        if channels_fmt := kw.get("channels_fmt"):
            self.channels_fmt = channels_fmt
        if datetime_fmt := kw.get("datetime_fmt"):
            self.datetime_fmt = datetime_fmt
        if entries_fmt := kw.get("entries_fmt"):
            self.entries_fmt = entries_fmt
        if feed_limit := kw.get("feed_limit"):
            self.feed_limit = feed_limit
        if (offset := int(kw.get("offset", 1))) > 1:
            self.offset = offset
        if separator := kw.get("separator"):
            self.separator = separator

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
