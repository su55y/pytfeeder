import dataclasses as dc
import logging
from os.path import expandvars
from pathlib import Path
from typing import Dict, List, Optional, Union
import shutil
import time

import yaml


from .defaults import (
    default_data_path,
    default_channels_filepath,
    default_lockfile_path,
)
from .models import Channel
from pytfeeder.rofi import ConfigRofi
from pytfeeder.tui import ConfigTUI

DEFAULT_LOG_FMT = (
    "[%(asctime)-.19s %(levelname)s] %(message)s (%(filename)s:%(lineno)d)"
)
LOGS_FILENAME = "pytfeeder.log"
STORAGE_FILENAME = "pytfeeder.db"

log_levels_map = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


def expand_path(path: Union[Path, str]) -> Path:
    return Path(expandvars(path)).expanduser()


@dc.dataclass
class Config:
    """Configuration settings

    Args:
        path (Path | str, optional): The path to the configuration file. If provided, the configuration will be loaded from the file.
    """

    channels_filepath: Path
    log_level: int
    log_file: Path
    log_fmt: str
    storage_path: Path
    rofi: ConfigRofi
    tui: ConfigTUI
    lock_file: Path
    __channels: List[Channel] = dc.field(default_factory=list, repr=False, kw_only=True)

    def __init__(
        self,
        config_file: Optional[Union[Path, str]] = None,
        channels_filepath: Optional[Path] = None,
        data_dir: Optional[Path] = None,
        channels: Optional[List[Channel]] = None,
        log_level: Optional[int] = None,
        log_file: Optional[Path] = None,
        log_fmt: Optional[str] = None,
        storage_path: Optional[Path] = None,
        rofi: Optional[ConfigRofi] = None,
        tui: Optional[ConfigTUI] = None,
        lock_file: Optional[Path] = None,
    ) -> None:
        self.__is_channels_set = False
        if channels is not None:
            self.channels = channels

        self.channels_filepath = channels_filepath or default_channels_filepath()
        if channels_filepath and channels is None:
            self.channels = self._load_channels_from_file(channels_filepath)

        self.data_dir = data_dir or default_data_path()
        self.log_level = log_level or logging.NOTSET
        self.log_file = log_file or self.data_dir.joinpath(LOGS_FILENAME)
        self.log_fmt = log_fmt or DEFAULT_LOG_FMT
        self.storage_path = storage_path or self.data_dir.joinpath(STORAGE_FILENAME)
        self.lock_file = lock_file or default_lockfile_path()
        self.rofi = rofi or ConfigRofi()
        self.tui = tui or ConfigTUI()

        if config_file:
            config_file = expand_path(config_file)
            if config_file.exists():
                self._override_defaults(config_file)

        if self.__is_channels_set is False:
            self.channels = self._load_channels_from_file(self.channels_filepath)

    @property
    def channels(self) -> List[Channel]:
        return self.__channels

    @channels.setter
    def channels(self, channels_: List[Channel]) -> None:
        assert isinstance(channels_, list), "Unexpected channels value type"
        self.__channels = channels_
        self.__is_channels_set = True

    def _override_defaults(self, config_path: Path) -> None:
        try:
            with config_path.open() as f:
                config_dict = yaml.safe_load(f)
            assert isinstance(
                config_dict, dict
            ), f"Unexpected config type {type(config_dict)!s}, should be dict"
        except Exception as e:
            print(f"Can't parse config {config_path}\n{e}")
            exit(1)

        if channels_filepath := config_dict.get("channels_filepath"):
            self.channels_filepath = expand_path(channels_filepath)

        if data_dir := config_dict.get("data_dir"):
            self.data_dir = expand_path(data_dir)
            self.log_file = self.data_dir.joinpath(LOGS_FILENAME)
            self.storage_path = self.data_dir.joinpath(STORAGE_FILENAME)

        if log_fmt := config_dict.get("log_fmt"):
            self.log_fmt = str(log_fmt)
        if isinstance((log_level := config_dict.get("log_level")), str):
            self.log_level = log_levels_map.get(log_level.lower(), self.log_level)
        if lock_file := config_dict.get("lock_file"):
            self.lock_file = expand_path(lock_file)
        if rofi_object := config_dict.get("rofi"):
            self.rofi.update(rofi_object)
        if tui_object := config_dict.get("tui"):
            self.tui.update(tui_object)

    def _load_channels_from_file(self, file: Path) -> List[Channel]:
        try:
            with file.open() as f:
                channels_ = [Channel(**c) for c in yaml.safe_load(f)]
                return channels_
        except Exception as e:
            print(f"Can't load channels: {e!s}")
            exit(1)

    def dump_channels(self) -> None:
        try:
            _ = shutil.copyfile(
                self.channels_filepath,
                self.channels_filepath.parent / f"channels{round(time.time())}.bak",
            )
            with self.channels_filepath.open("w") as f:
                yaml.safe_dump([c.dump() for c in self.channels], f, allow_unicode=True)
        except Exception as e:
            print(f"Can't dump channels: {e!s}")
            exit(1)

    def __repr__(self) -> str:
        repr_str = ""
        repr_str += f"data_dir: {self.data_dir!s}\n"
        if self.channels:
            repr_str += "channels:\n"
            repr_str += "".join(
                f"  - {{ channel_id: {c.channel_id}, title: {c.title!r} }}\n"
                for c in self.channels
            )
        repr_str += f"log_fmt: {self.log_fmt!r}\n"
        log_level_name = {v: k for k, v in log_levels_map.items()}.get(self.log_level)
        repr_str += f"log_level: {log_level_name}\n"
        repr_str += f"{repr(self.rofi).strip()}\n"
        repr_str += f"{repr(self.tui).strip()}\n"
        return repr_str.strip()
