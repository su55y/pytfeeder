import dataclasses as dc
import os
from pathlib import Path
import tempfile
import shutil

import yaml

from .defaults import (
    default_data_path,
    default_channels_filepath,
    default_lockfile_path,
)
from .logger import LoggerConfig
from .models import Channel
from .utils import expand_path
from pytfeeder.rofi import ConfigRofi
from pytfeeder.tui import ConfigTUI


STORAGE_FILENAME = "pytfeeder.db"


@dc.dataclass
class Config:
    channels_filepath: Path
    logger: LoggerConfig
    storage_path: Path
    rofi: ConfigRofi
    tui: ConfigTUI
    lock_file: Path
    __channels: list[Channel] = dc.field(default_factory=list, repr=False, kw_only=True)

    def __init__(
        self,
        config_file: Path | None = None,
        channels_filepath: Path | None = None,
        data_dir: Path | None = None,
        channels: list[Channel] | None = None,
        logger_config: LoggerConfig | None = None,
        storage_path: Path | None = None,
        rofi: ConfigRofi | None = None,
        tui: ConfigTUI | None = None,
        lock_file: Path | None = None,
    ) -> None:
        self.__is_channels_set = False
        if channels is not None:
            self.channels = channels

        self.channels_filepath = channels_filepath or default_channels_filepath()
        if channels_filepath and channels is None:
            self.channels = self._load_channels_from_file(channels_filepath)

        self.lock_file = lock_file or default_lockfile_path()
        self.logger = logger_config or LoggerConfig()
        self.rofi = rofi or ConfigRofi()
        self.tui = tui or ConfigTUI()

        self.__is_data_dir_set = False
        if config_file and (config_file := expand_path(config_file)).exists():
            self._parse_config_file(config_file)

        self._set_data_paths(
            data_dir=data_dir,
            storage_path=storage_path,
        )
        if self.__is_channels_set is False:
            self.channels = self._load_channels_from_file(self.channels_filepath)

    @property
    def channels(self) -> list[Channel]:
        return self.__channels

    @channels.setter
    def channels(self, channels_: list[Channel]) -> None:
        assert isinstance(channels_, list), "Unexpected channels value type"
        self.__channels = channels_
        self.__is_channels_set = True

    def _parse_config_file(self, config_path: Path) -> None:
        try:
            with config_path.open() as f:
                config_dict = yaml.safe_load(f)
            assert isinstance(
                config_dict, dict
            ), f"Unexpected config type {type(config_dict)}, should be dict"
        except Exception as e:
            raise Exception(f"Error while parsing {config_path}\n{e!r}")

        if channels_filepath := config_dict.get("channels_filepath"):
            self.channels_filepath = expand_path(channels_filepath)

        if data_dir := config_dict.get("data_dir"):
            self.data_dir = expand_path(data_dir)
            self.storage_path = self.data_dir.joinpath(STORAGE_FILENAME)
            self.__is_data_dir_set = True

        if lock_file := config_dict.get("lock_file"):
            self.lock_file = expand_path(lock_file)
        if logger_object := config_dict.get("logger"):
            self.logger.update(logger_object)
        if rofi_object := config_dict.get("rofi"):
            self.rofi.update(rofi_object)
        if tui_object := config_dict.get("tui"):
            self.tui.update(tui_object)

    def _set_data_paths(
        self,
        data_dir: Path | None = None,
        storage_path: Path | None = None,
    ) -> None:
        if data_dir:
            self.data_dir = expand_path(data_dir)
        elif not self.__is_data_dir_set:
            self.data_dir = default_data_path()

        if storage_path:
            self.storage_path = expand_path(storage_path)
        else:
            self.storage_path = self.data_dir.joinpath(STORAGE_FILENAME)

    def _load_channels_from_file(self, file: Path) -> list[Channel]:
        try:
            with file.open() as f:
                channels_list = yaml.safe_load(f)
                if channels_list is None:
                    return []
                if not isinstance(channels_list, list):
                    raise ValueError(
                        f"Unexpected channels file yaml format ({type(channels_list)}), should be collection of channels"
                    )
                channels_ = [Channel(**c) for c in channels_list]
                return channels_
        except Exception as e:
            raise Exception(f"Error while loading channels: {e!r}")

    def dump_channels(self) -> None:
        fd, tmp_name = tempfile.mkstemp(prefix="channels", suffix=".yaml")
        os.close(fd)
        try:
            _ = shutil.copyfile(self.channels_filepath, tmp_name)
            with self.channels_filepath.open("w") as f:
                yaml.safe_dump([c.dump() for c in self.channels], f, allow_unicode=True)
        except Exception as e:
            raise Exception(
                f"Error while dumping channels: {e!s}\nBackup copied to {tmp_name}"
            )
        else:
            os.remove(tmp_name)

    def __repr__(self) -> str:
        repr_str = ""
        repr_str += f"channels_filepath: {self.channels_filepath!s}\n"
        repr_str += f"data_dir: {self.data_dir!s}\n"

        if self.channels:
            repr_str += "channels:\n"
            repr_str += "".join(
                f"  - {{ channel_id: {c.channel_id}, title: {c.title!r} }}\n"
                for c in self.channels
            )
        else:
            repr_str += "channels: []\n"

        repr_str += f"{repr(self.logger).strip()}\n"
        repr_str += f"{repr(self.rofi).strip()}\n"
        repr_str += f"{repr(self.tui).strip()}\n"
        return repr_str.strip()
