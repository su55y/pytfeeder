from dataclasses import dataclass
from typing import Any, Dict, Optional

DEFAULT_CHANNELS_FMT = "{new_mark} | {title}"
DEFAULT_ENTRIES_FMT = "{new_mark} | {updated} | {title}"
DEFAULT_FEED_ENTRIES_FMT = "{new_mark} | {updated} | {channel_title} | {title}"
DEFAULT_LAST_UPDATE_FMT = "%D %T"
DEFAULT_STATUS_FMT = "{msg}{index} {title} {keybinds}"


@dataclass
class ConfigTUI:
    always_update: bool = False
    channels_fmt: str = DEFAULT_CHANNELS_FMT
    entries_fmt: str = DEFAULT_ENTRIES_FMT
    feed_entries_fmt: str = DEFAULT_FEED_ENTRIES_FMT
    hide_feed: bool = False
    last_update_fmt: str = DEFAULT_LAST_UPDATE_FMT
    status_fmt: str = DEFAULT_STATUS_FMT
    update_interval: Optional[int] = None
    macro1: str = ""
    macro2: str = ""
    macro3: str = ""
    macro4: str = ""

    def parse_kwargs(self, kw: Dict[str, Any]) -> None:
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

    def __repr__(self) -> str:
        repr_str = "tui:\n"
        repr_str += f"  always_update: {self.always_update}\n"
        repr_str += f"  channels_fmt: {self.channels_fmt!r}\n"
        repr_str += f"  entries_fmt: {self.entries_fmt!r}\n"
        repr_str += f"  feed_entries_fmt: {self.feed_entries_fmt!r}\n"
        repr_str += f"  hide_feed: {self.hide_feed}\n"
        repr_str += f"  last_update_fmt: {self.last_update_fmt!r}\n"
        repr_str += f"  status_fmt: {self.status_fmt!r}\n"
        repr_str += f"  update_interval: {self.update_interval}\n"
        repr_str += f"  macro1: {self.macro1}\n"
        repr_str += f"  macro2: {self.macro2}\n"
        repr_str += f"  macro3: {self.macro3}\n"
        repr_str += f"  macro4: {self.macro4}\n"
        return repr_str
