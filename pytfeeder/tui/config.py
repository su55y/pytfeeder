from dataclasses import dataclass
from typing import Any

from . import consts


@dataclass
class ConfigTUI:
    always_update: bool = False
    alphabetic_sort: bool = False
    color_accent: str | int = "red"
    color_black: str | int = "black"
    color_white: str | int = "white"
    channels_fmt: str = consts.DEFAULT_CHANNELS_FMT
    channel_feed_limit: int = -1
    datetime_fmt: str = consts.DEFAULT_DATETIME_FMT
    download_output: str = consts.DEFAULT_DOWNLOAD_OUTPUT
    entries_fmt: str = consts.DEFAULT_ENTRIES_FMT
    feed_entries_fmt: str = consts.DEFAULT_FEED_ENTRIES_FMT
    feed_limit: int = -1
    hide_empty: bool = False
    hide_feed: bool = False
    hide_statusbar: bool = False
    last_update_fmt: str = consts.DEFAULT_LAST_UPDATE_FMT
    new_mark: str = consts.DEFAULT_NEW_MARK
    no_update: bool = False
    status_fmt: str = consts.DEFAULT_STATUS_FMT
    unwatched_first: bool = False
    update_interval: int = consts.DEFAULT_UPDATE_INTERVAL_MINS
    macro1: str = ""
    macro2: str = ""
    macro3: str = ""
    macro4: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.color_accent, str):
            self.color_accent = self.color_accent.lower()
        if isinstance(self.color_black, str):
            self.color_black = self.color_black.lower()
        if isinstance(self.color_white, str):
            self.color_white = self.color_white.lower()

    def update(self, kwargs: dict[str, Any]) -> None:
        for k, v in kwargs.items():
            if k in vars(self) and v is not None:
                if k.startswith("color_") and isinstance(v, str):
                    v = v.lower()
                if isinstance(v, bool):
                    v = getattr(self, k, v) | v
                setattr(self, k, v)

    def __repr__(self) -> str:
        repr_str = "tui:\n"
        for k, v in sorted(vars(self).items()):
            repr_str += f"  {k}: {v!r}\n"
        return repr_str
