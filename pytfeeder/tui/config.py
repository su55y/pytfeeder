from dataclasses import dataclass
from typing import Any, Dict

from . import consts


@dataclass
class ConfigTUI:
    always_update: bool = False
    channels_fmt: str = consts.DEFAULT_CHANNELS_FMT
    entries_fmt: str = consts.DEFAULT_ENTRIES_FMT
    feed_entries_fmt: str = consts.DEFAULT_FEED_ENTRIES_FMT
    hide_feed: bool = False
    last_update_fmt: str = consts.DEFAULT_LAST_UPDATE_FMT
    new_mark: str = consts.DEFAULT_NEW_MARK
    status_fmt: str = consts.DEFAULT_STATUS_FMT
    update_interval: int = consts.DEFAULT_UPDATE_INTERVAL_MINS
    macro1: str = ""
    macro2: str = ""
    macro3: str = ""
    macro4: str = ""

    def parse_config_file(self, kw: Dict[str, Any]) -> None:
        if always_update := kw.get("always_update"):
            self.always_update = bool(always_update)
        if channels_fmt := kw.get("channels_fmt"):
            self.channels_fmt = channels_fmt
        if entries_fmt := kw.get("entries_fmt"):
            self.entries_fmt = entries_fmt
        if feed_entries_fmt := kw.get("feed_entries_fmt"):
            self.feed_entries_fmt = feed_entries_fmt
        if hide_feed := kw.get("hide_feed"):
            self.hide_feed = hide_feed
        if last_update_fmt := kw.get("last_update_fmt"):
            self.last_update_fmt = last_update_fmt
        if new_mark := kw.get("new_mark"):
            self.new_mark = new_mark
        if status_fmt := kw.get("status_fmt"):
            self.status_fmt = status_fmt
        if update_interval := kw.get("update_interval"):
            self.update_interval = update_interval
        if macro1 := kw.get("macro1"):
            self.macro1 = macro1
        if macro2 := kw.get("macro2"):
            self.macro2 = macro2
        if macro3 := kw.get("macro3"):
            self.macro3 = macro3
        if macro4 := kw.get("macro4"):
            self.macro4 = macro4

    def parse_args(self, kw: Dict[str, Any]) -> None:
        if channels_fmt := kw.get("channels_fmt"):
            self.channels_fmt = channels_fmt
        if entries_fmt := kw.get("entries_fmt"):
            self.entries_fmt = entries_fmt
        if feed_entries_fmt := kw.get("feed_entries_fmt"):
            self.feed_entries_fmt = feed_entries_fmt
        if hide_feed := kw.get("hide_feed"):
            self.hide_feed = hide_feed
        if last_update_fmt := kw.get("last_update_fmt"):
            self.last_update_fmt = last_update_fmt
        if status_fmt := kw.get("status_fmt"):
            self.status_fmt = status_fmt
        if m1 := kw.get("macro1"):
            self.macro1 = m1
        if m2 := kw.get("macro2"):
            self.macro2 = m2
        if m3 := kw.get("macro3"):
            self.macro1 = m3
        if m4 := kw.get("macro4"):
            self.macro1 = m4

    def __repr__(self) -> str:
        repr_str = "tui:\n"
        repr_str += f"  always_update: {self.always_update}\n"
        repr_str += f"  channels_fmt: {self.channels_fmt!r}\n"
        repr_str += f"  entries_fmt: {self.entries_fmt!r}\n"
        repr_str += f"  feed_entries_fmt: {self.feed_entries_fmt!r}\n"
        repr_str += f"  hide_feed: {self.hide_feed}\n"
        repr_str += f"  last_update_fmt: {self.last_update_fmt!r}\n"
        repr_str += f"  new_mark: {self.new_mark!r}\n"
        repr_str += f"  status_fmt: {self.status_fmt!r}\n"
        repr_str += f"  update_interval: {self.update_interval}\n"
        repr_str += f"  macro1: {self.macro1}\n"
        repr_str += f"  macro2: {self.macro2}\n"
        repr_str += f"  macro3: {self.macro3}\n"
        repr_str += f"  macro4: {self.macro4}\n"
        return repr_str
