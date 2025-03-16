import dataclasses as dc
import logging
from os.path import expandvars
from pathlib import Path
from typing import Dict, List, Optional, Union
import shutil
import time

import yaml


from .defaults import (
    default_cachedir_path,
    default_channels_filepath,
    default_lockfile_path,
)
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


def load_channels(path: Path) -> List[Channel]:
    try:
        return [Channel(**c) for c in yaml.safe_load(path.open())]
    except Exception as e:
        print(f"Can't load channels: {e!s}")
        exit(1)


@dc.dataclass
class Config:
    """Configuration settings

    Args:
        path (Path | str, optional): The path to the configuration file. If provided, the configuration will be loaded from the file.
    """

    channels: List[Channel]
    channels_filepath: Path
    log_level: int
    log_file: Path
    log_fmt: str
    storage_path: Path
    rofi: ConfigRofi
    tui: ConfigTUI
    lock_file: Path

    def __init__(
        self,
        config_file: Optional[Union[Path, str]] = None,
        channels_filepath: Optional[Path] = None,
        cache_dir: Optional[Path] = None,
        channels: Optional[List[Channel]] = None,
        log_level: Optional[int] = None,
        log_file: Optional[Path] = None,
        log_fmt: Optional[str] = None,
        storage_path: Optional[Path] = None,
        rofi: ConfigRofi = ConfigRofi(),
        tui: ConfigTUI = ConfigTUI(),
        lock_file: Optional[Path] = None,
    ) -> None:
        self.channels = channels or []
        self.channels_filepath = channels_filepath or default_channels_filepath()
        self.cache_dir = cache_dir or default_cachedir_path()
        self.log_level = log_level or logging.NOTSET
        self.log_file = log_file or self.cache_dir.joinpath("pytfeeder.log")
        self.log_fmt = log_fmt or DEFAULT_LOG_FMT
        self.storage_path = storage_path or self.cache_dir.joinpath("pytfeeder.db")
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

        if channels_filepath := config_dict.get("channels_filepath"):
            self.channels_filepath = expand_path(channels_filepath)
        self.channels = load_channels(self.channels_filepath)

        if cache_dir := config_dict.get("cache_dir"):
            self.cache_dir = expand_path(cache_dir)
            self.log_file = self.cache_dir.joinpath("pytfeeder.log")
            self.storage_path = self.cache_dir.joinpath("pytfeeder.db")
        if log_fmt := config_dict.get("log_fmt"):
            self.log_fmt = str(log_fmt)
        if isinstance((log_level := config_dict.get("log_level")), str):
            self.log_level = log_levels_map.get(log_level.lower(), logging.NOTSET)
        if lock_file := config_dict.get("lock_file"):
            self.lock_file = expand_path(lock_file)
        if rofi_object := config_dict.get("rofi"):
            self.rofi.update(rofi_object)
        if tui_object := config_dict.get("tui"):
            self.tui.update(tui_object)

    def dump_channels(self) -> None:
        try:
            _ = shutil.copyfile(
                self.channels_filepath,
                self.channels_filepath.parent / f"channels{round(time.time())}.bak",
            )
            yaml.safe_dump(
                [c.dump() for c in self.channels],
                self.channels_filepath.open("w"),
                allow_unicode=True,
            )
        except Exception as e:
            print(f"Can't dump channels: {e!s}")
            exit(1)

    def __dump(self, config_file: str) -> None:
        data = {
            "cache_dir": str(self.cache_dir),
            "channels_filepath": str(self.channels_filepath),
            "log_fmt": self.log_fmt,
            "log_level": self.log_level,
            "rofi": dc.asdict(self.rofi),
            "tui": dc.asdict(self.tui),
        }
        with open(config_file, "w") as f:
            yaml.safe_dump(data, f, allow_unicode=True)

    def __repr__(self) -> str:
        repr_str = ""
        repr_str += f"cache_dir: {self.cache_dir!s}\n"
        if self.channels:
            repr_str += "channels:\n"
            repr_str += "".join(
                f"  - {{ channel_id: {c.channel_id}, title: {c.title!r} }}\n"
                for c in self.channels
            )
        repr_str += f"log_fmt: {self.log_fmt!r}\n"
        repr_str += f"log_level: {self.log_level}\n"
        repr_str += f"{repr(self.rofi).strip()}\n"
        repr_str += f"{repr(self.tui).strip()}\n"
        return repr_str.strip()
