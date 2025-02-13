from dataclasses import dataclass, asdict
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from os.path import expandvars

import yaml

from .defaults import default_cachedir_path, default_lockfile_path
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


def expand_path(path: Union[Path, str]) -> Path:
    return Path(expandvars(path)).expanduser()


@dataclass
class Config:
    """Configuration settings

    Args:
        path (Path | str, optional): The path to the configuration file. If provided, the configuration will be loaded from the file.
    """

    channels: List[Channel]
    alphabetic_sort: bool
    datetime_fmt: str
    log_level: int
    log_file: Path
    log_fmt: str
    storage_path: Path
    rofi_channels_fmt: str
    rofi_entries_fmt: str
    unviewed_first: bool
    tui: ConfigTUI
    update_lock_file: Path
    channel_feed_limit: Optional[int] = None
    feed_limit: Optional[int] = None

    def __init__(
        self,
        config_file: Optional[Union[Path, str]] = None,
        cache_dir: Optional[Path] = None,
        channels: Optional[List[Channel]] = None,
        channel_feed_limit: Optional[int] = None,
        datetime_fmt: Optional[str] = None,
        feed_limit: Optional[int] = None,
        log_level: Optional[int] = None,
        log_file: Optional[Path] = None,
        log_fmt: Optional[str] = None,
        storage_path: Optional[Path] = None,
        rofi_entries_fmt: Optional[str] = None,
        rofi_channels_fmt: Optional[str] = None,
        alphabetic_sort: Optional[bool] = None,
        unviewed_first: Optional[bool] = None,
        tui: ConfigTUI = ConfigTUI(),
        update_lock_file: Optional[Path] = None,
    ) -> None:
        self.channels = channels or []
        self.feed_limit = feed_limit
        self.channel_feed_limit = channel_feed_limit
        self.cache_dir = cache_dir or default_cachedir_path()
        self.datetime_fmt = datetime_fmt or DEFAULT_DATETIME_FMT
        self.log_level = log_level or logging.NOTSET
        self.log_file = log_file or self.cache_dir.joinpath("pytfeeder.log")
        self.log_fmt = log_fmt or DEFAULT_LOG_FMT
        self.storage_path = storage_path or self.cache_dir.joinpath("pytfeeder.db")
        self.rofi_channels_fmt = rofi_channels_fmt or DEFAULT_ROFI_CHANNELS_FMT
        self.rofi_entries_fmt = rofi_entries_fmt or DEFAULT_ROFI_ENTRIES_FMT
        self.alphabetic_sort = alphabetic_sort or False
        self.unviewed_first = unviewed_first or False
        self.update_lock_file = update_lock_file or default_lockfile_path()
        self.tui = tui
        if config_file:
            config_file = expand_path(config_file)
            if config_file.exists():
                self._override_defaults(config_file)

    def _override_defaults(self, config_path: Path) -> None:
        try:
            config_dict = yaml.safe_load(config_path.open())
        except Exception as e:
            exit("Invalid config %s: %s" % (config_path, e))

        if not isinstance(config_dict, Dict):
            print("Invalid config format (type: %s)" % type(config_dict))
            exit(1)

        self.channels = [Channel(**c) for c in config_dict.get("channels", [])]
        if cache_dir := config_dict.get("cache_dir"):
            self.cache_dir = expand_path(cache_dir)
            self.log_file = self.cache_dir.joinpath("pytfeeder.log")
            self.storage_path = self.cache_dir.joinpath("pytfeeder.db")
        if log_fmt := config_dict.get("log_fmt"):
            self.log_fmt = str(log_fmt)
        if isinstance((log_level := config_dict.get("log_level")), str):
            self.log_level = log_levels_map.get(log_level.lower(), logging.NOTSET)
        if feed_limit := config_dict.get("feed_limit"):
            self.feed_limit = int(feed_limit)
        if channel_feed_limit := config_dict.get("channel_feed_limit"):
            self.channel_feed_limit = int(channel_feed_limit)
        if datetime_fmt := config_dict.get("datetime_fmt"):
            self.datetime_fmt = datetime_fmt
        if rofi_channels_fmt := config_dict.get("rofi_channels_fmt"):
            self.rofi_channels_fmt = rofi_channels_fmt
        if rofi_entries_fmt := config_dict.get("rofi_entries_fmt"):
            self.rofi_entries_fmt = rofi_entries_fmt
        if alphabetic_sort := config_dict.get("alphabetic_sort"):
            self.alphabetic_sort = bool(alphabetic_sort)
        if unviewed_first := config_dict.get("unviewed_first"):
            self.unviewed_first = bool(unviewed_first)
        if update_lock_file := config_dict.get("update_lock_file"):
            self.update_lock_file = expand_path(update_lock_file)
        if tui_object := config_dict.get("tui"):
            self.tui.parse_config_file(tui_object)

    def parse_args(self, kw: Dict[str, Any]) -> None:
        if limit := kw.get("limit"):
            self.channel_feed_limit = limit
        if feed_limit := kw.get("feed_limit"):
            self.feed_limit = feed_limit
        if alphabetic_sort := kw.get("alphabetic_sort"):
            self.alphabetic_sort = alphabetic_sort
        if datetime_fmt := kw.get("datetime_fmt"):
            self.datetime_fmt = datetime_fmt

    def dump(self, config_file: str) -> None:
        data = {
            "alphabetic_sort": self.alphabetic_sort,
            "cache_dir": str(self.cache_dir),
            "channels": [c.dump() for c in self.channels],
            "channel_feed_limit": self.channel_feed_limit,
            "datetime_fmt": self.datetime_fmt,
            "feed_limit": self.feed_limit,
            "log_fmt": self.log_fmt,
            "log_level": self.log_level,
            "rofi_channels_fmt": self.rofi_channels_fmt,
            "rofi_entries_fmt": self.rofi_entries_fmt,
            "unviewed_first": self.unviewed_first,
            "tui": asdict(self.tui),
        }
        with open(config_file, "w") as f:
            yaml.safe_dump(data, f, allow_unicode=True)

    def __repr__(self) -> str:
        repr_str = ""
        repr_str += f"alphabetic_sort: {self.alphabetic_sort}\n"
        repr_str += f"cache_dir: {self.cache_dir!s}\n"
        if self.channels:
            repr_str += "channels:\n"
            repr_str += "".join(
                f"  - {{ channel_id: {c.channel_id}, title: {c.title!r} }}\n"
                for c in self.channels
            )
        repr_str += f"channel_feed_limit: {self.channel_feed_limit}\n"
        repr_str += f"datetime_fmt: {self.datetime_fmt!r}\n"
        repr_str += f"feed_limit: {self.feed_limit}\n"
        repr_str += f"log_fmt: {self.log_fmt!r}\n"
        repr_str += f"log_level: {self.log_level}\n"
        repr_str += f"rofi_channels_fmt: {self.rofi_channels_fmt!r}\n"
        repr_str += f"rofi_entries_fmt: {self.rofi_entries_fmt!r}\n"
        repr_str += f"unviewed_first: {self.unviewed_first}\n"
        repr_str += repr(self.tui)
        return repr_str.strip()
