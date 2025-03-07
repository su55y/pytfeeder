from dataclasses import dataclass, asdict
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from os.path import expandvars

import yaml


from .defaults import default_cachedir_path, default_lockfile_path
from .models import Channel
from .consts import DEFAULT_LOG_FMT
from pytfeeder.rofi import ConfigRofi
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
    log_level: int
    log_file: Path
    log_fmt: str
    storage_path: Path
    unwatched_first: bool
    rofi: ConfigRofi
    tui: ConfigTUI
    lock_file: Path

    def __init__(
        self,
        config_file: Optional[Union[Path, str]] = None,
        cache_dir: Optional[Path] = None,
        channels: Optional[List[Channel]] = None,
        log_level: Optional[int] = None,
        log_file: Optional[Path] = None,
        log_fmt: Optional[str] = None,
        storage_path: Optional[Path] = None,
        alphabetic_sort: Optional[bool] = None,
        unwatched_first: Optional[bool] = None,
        rofi: ConfigRofi = ConfigRofi(),
        tui: ConfigTUI = ConfigTUI(),
        lock_file: Optional[Path] = None,
    ) -> None:
        self.channels = channels or []
        self.cache_dir = cache_dir or default_cachedir_path()
        self.log_level = log_level or logging.NOTSET
        self.log_file = log_file or self.cache_dir.joinpath("pytfeeder.log")
        self.log_fmt = log_fmt or DEFAULT_LOG_FMT
        self.storage_path = storage_path or self.cache_dir.joinpath("pytfeeder.db")
        self.alphabetic_sort = alphabetic_sort or False
        self.unwatched_first = unwatched_first or False
        self.lock_file = lock_file or default_lockfile_path()
        self.rofi = rofi
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
        if alphabetic_sort := config_dict.get("alphabetic_sort"):
            self.alphabetic_sort = bool(alphabetic_sort)
        if unwatched_first := config_dict.get("unwatched_first"):
            self.unwatched_first = bool(unwatched_first)
        if lock_file := config_dict.get("lock_file"):
            self.lock_file = expand_path(lock_file)
        if rofi_object := config_dict.get("rofi"):
            self.rofi.parse_config_file(rofi_object)
        if tui_object := config_dict.get("tui"):
            self.tui.parse_config_file(tui_object)

    def parse_args(self, kw: Dict[str, Any]) -> None:
        if alphabetic_sort := kw.get("alphabetic_sort"):
            self.alphabetic_sort = alphabetic_sort
        if unwatched_first := kw.get("unwatched_first"):
            self.unwatched_first = unwatched_first

    def dump(self, config_file: str) -> None:
        data = {
            "alphabetic_sort": self.alphabetic_sort,
            "cache_dir": str(self.cache_dir),
            "channels": [c.dump() for c in self.channels],
            "log_fmt": self.log_fmt,
            "log_level": self.log_level,
            "unwatched_first": self.unwatched_first,
            "rofi": asdict(self.rofi),
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
        repr_str += f"log_fmt: {self.log_fmt!r}\n"
        repr_str += f"log_level: {self.log_level}\n"
        repr_str += f"unwatched_first: {self.unwatched_first}\n"
        repr_str += repr(self.tui)
        return repr_str.strip()
