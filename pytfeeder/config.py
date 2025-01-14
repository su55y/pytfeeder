from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union
from os.path import expandvars

import yaml

from .defaults import default_cachedir_path
from .models import Channel
from .consts import (
    DEFAULT_ROFI_CHANNELS_FMT,
    DEFAULT_ROFI_ENTRIES_FMT,
    DEFAULT_LOG_FMT,
    DEFAULT_DATETIME_FMT,
)
from pytfeeder.tui import ConfigTUI


log_levels_map = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


def read_config(file: Path) -> Dict:
    try:
        with open(file) as f:
            return yaml.safe_load(f)
    except Exception as e:
        exit("invalid config %s: %s" % (file, e))


def expand_path(path: Union[Path, str]) -> Path:
    return Path(expandvars(path)).expanduser()


@dataclass
class Config:
    """Configuration settings

    Args:
        path (Path | str, optional): The path to the configuration file. If provided, the configuration will be loaded from the file.
    """

    channels: List[Channel]
    channels_fmt: str
    entries_fmt: str
    feed_entries_fmt: str
    log_level: int
    log_file: Path
    log_fmt: str
    storage_path: Path
    rofi_channels_fmt: str
    rofi_entries_fmt: str
    alphabetic_sort: bool
    unviewed_first: bool
    always_update: bool
    tui: ConfigTUI
    channel_feed_limit: Optional[int] = None
    feed_limit: Optional[int] = None
    update_interval: Optional[int] = None

    def __init__(
        self,
        config_file: Optional[Union[Path, str]] = None,
        cache_dir: Optional[Path] = None,
        channels: Optional[List[Channel]] = None,
        channel_feed_limit: Optional[int] = None,
        channels_fmt: Optional[str] = None,
        datetime_fmt: Optional[str] = None,
        entries_fmt: Optional[str] = None,
        feed_entries_fmt: Optional[str] = None,
        feed_limit: Optional[int] = None,
        log_level: Optional[int] = None,
        log_file: Optional[Path] = None,
        log_fmt: Optional[str] = None,
        storage_path: Optional[Path] = None,
        rofi_entries_fmt: Optional[str] = None,
        rofi_channels_fmt: Optional[str] = None,
        alphabetic_sort: Optional[bool] = None,
        always_update: Optional[bool] = None,
        unviewed_first: Optional[bool] = None,
        update_interval: Optional[int] = None,
        tui: ConfigTUI = ConfigTUI(),
    ) -> None:
        self.channels = channels or []
        self.feed_limit = feed_limit
        self.channel_feed_limit = channel_feed_limit
        self.cache_dir = cache_dir or default_cachedir_path()
        self.channels_fmt = channels_fmt or ""
        self.datetime_fmt = datetime_fmt or DEFAULT_DATETIME_FMT
        self.entries_fmt = entries_fmt or ""
        self.feed_entries_fmt = feed_entries_fmt or ""
        self.log_level = log_level or logging.NOTSET
        self.log_file = log_file or self.cache_dir.joinpath("pytfeeder.log")
        self.log_fmt = log_fmt or DEFAULT_LOG_FMT
        self.storage_path = storage_path or self.cache_dir.joinpath("pytfeeder.db")
        self.rofi_channels_fmt = rofi_channels_fmt or DEFAULT_ROFI_CHANNELS_FMT
        self.rofi_entries_fmt = rofi_entries_fmt or DEFAULT_ROFI_ENTRIES_FMT
        self.alphabetic_sort = alphabetic_sort or False
        self.always_update = always_update or False
        self.unviewed_first = unviewed_first or False
        self.update_interval = update_interval or None
        self.tui = tui
        if config_file:
            config_file = expand_path(config_file)
            if config_file.exists():
                self._override_defaults(config_file)

    def _override_defaults(self, config_path: Path) -> None:
        config = read_config(config_path)
        if not isinstance(config, Dict):
            print("Invalid config file given")
            exit(1)
        self.channels = [Channel(**c) for c in config.get("channels", [])]
        if cache_dir := config.get("cache_dir"):
            self.cache_dir = expand_path(cache_dir)
            self.log_file = self.cache_dir.joinpath("pytfeeder.log")
            self.storage_path = self.cache_dir.joinpath("pytfeeder.db")
        if log_fmt := config.get("log_fmt"):
            self.log_fmt = str(log_fmt)
        if isinstance((log_level := config.get("log_level")), str):
            self.log_level = log_levels_map.get(log_level.lower(), logging.NOTSET)
        if feed_limit := config.get("feed_limit"):
            self.feed_limit = int(feed_limit)
        if channel_feed_limit := config.get("channel_feed_limit"):
            self.channel_feed_limit = int(channel_feed_limit)
        if channels_fmt := config.get("channels_fmt"):
            self.channels_fmt = channels_fmt
        if entries_fmt := config.get("entries_fmt"):
            self.entries_fmt = entries_fmt
        if feed_entries_fmt := config.get("feed_entries_fmt"):
            self.feed_entries_fmt = feed_entries_fmt
        if datetime_fmt := config.get("datetime_fmt"):
            self.datetime_fmt = datetime_fmt
        if rofi_channels_fmt := config.get("rofi_channels_fmt"):
            self.rofi_channels_fmt = rofi_channels_fmt
        if rofi_entries_fmt := config.get("rofi_entries_fmt"):
            self.rofi_entries_fmt = rofi_entries_fmt
        if alphabetic_sort := config.get("alphabetic_sort"):
            self.alphabetic_sort = bool(alphabetic_sort)
        if always_update := config.get("always_update"):
            self.always_update = bool(always_update)
        if unviewed_first := config.get("unviewed_first"):
            self.unviewed_first = bool(unviewed_first)
        if update_interval := config.get("update_interval"):
            self.update_interval = update_interval
        self.tui.parse_kwargs(config)

    def dump(self, config_file: str) -> None:
        data = {
            "alphabetic_sort": self.alphabetic_sort,
            "always_update": self.always_update,
            "cache_dir": str(self.cache_dir),
            "channels": [c.dump() for c in self.channels],
            "channels_fmt": self.channels_fmt,
            "channel_feed_limit": self.channel_feed_limit,
            "entries_fmt": self.entries_fmt,
            "feed_entries_fmt": self.feed_entries_fmt,
            "datetime_fmt": self.datetime_fmt,
            "feed_limit": self.feed_limit,
            "log_fmt": self.log_fmt,
            "log_level": self.log_level,
            "rofi_channels_fmt": self.rofi_channels_fmt,
            "rofi_entries_fmt": self.rofi_entries_fmt,
            "unviewed_first": self.unviewed_first,
            "update_interval": self.update_interval,
            "macro1": self.tui.macro1,
            "macro2": self.tui.macro2,
            "macro3": self.tui.macro3,
            "macro4": self.tui.macro4,
        }
        with open(config_file, "w") as f:
            yaml.safe_dump(data, f, allow_unicode=True)

    def __repr__(self) -> str:
        repr_str = ""
        repr_str += f"alphabetic_sort: {self.alphabetic_sort}\n"
        repr_str += f"always_update: {self.always_update}\n"
        repr_str += f"cache_dir: {self.cache_dir!s}\n"
        if self.channels:
            repr_str += "channels:\n"
            repr_str += "".join(
                f"  - {{ channel_id: {c.channel_id}, title: {c.title!r} }}\n"
                for c in self.channels
            )
        repr_str += f"channel_feed_limit: {self.channel_feed_limit}\n"
        repr_str += f"channels_fmt: {self.channels_fmt!r}\n"
        repr_str += f"entries_fmt: {self.entries_fmt!r}\n"
        repr_str += f"datetime_fmt: {self.datetime_fmt!r}\n"
        repr_str += f"feed_entries_fmt: {self.feed_entries_fmt!r}\n"
        repr_str += f"feed_limit: {self.feed_limit}\n"
        repr_str += f"log_fmt: {self.log_fmt!r}\n"
        repr_str += f"log_level: {self.log_level}\n"
        repr_str += f"rofi_channels_fmt: {self.rofi_channels_fmt!r}\n"
        repr_str += f"rofi_entries_fmt: {self.rofi_entries_fmt!r}\n"
        repr_str += f"unviewed_first: {self.unviewed_first}\n"
        repr_str += f"update_interval: {self.update_interval}\n"
        repr_str += f"macro1: {self.tui.macro1!r}\n"
        repr_str += f"macro2: {self.tui.macro2!r}\n"
        repr_str += f"macro3: {self.tui.macro3!r}\n"
        repr_str += f"macro4: {self.tui.macro4!r}\n"
        return repr_str.strip()
