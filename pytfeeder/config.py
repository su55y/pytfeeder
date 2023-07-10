from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union
from os.path import expanduser, expandvars

import yaml

from .dirs import default_storage_path, default_logfile_path
from .models import Channel


LOG_FMT = "[%(asctime)-.19s %(levelname)s] %(message)s (%(filename)s:%(lineno)d)"


@dataclass
class Config:
    """Configuration settings

    Args:
        path (Path | str, optional): The path to the configuration file. If provided, the configuration will be loaded from the file.
    """

    channels: List[Channel]
    storage_path: Path
    log_level: int
    log_file: Path
    log_fmt: str
    feed_limit: Optional[int] = None
    channel_feed_limit: Optional[int] = None

    def __init__(
        self,
        path: Optional[Union[Path, str]] = None,
        channels: Optional[List[Channel]] = None,
        feed_limit: Optional[int] = None,
        channel_feed_limit: Optional[int] = None,
        log_level: Optional[int] = None,
        log_file: Optional[Path] = None,
        log_fmt: Optional[str] = None,
        storage_path: Optional[Path] = None,
    ) -> None:
        self.channels = channels or []
        self.feed_limit = feed_limit
        self.channel_feed_limit = channel_feed_limit
        self.log_level = log_level or 0
        self.log_file = log_file or default_logfile_path()
        self.log_fmt = log_fmt or LOG_FMT
        self.storage_path = storage_path or default_storage_path()
        if path:
            self._override_defaults(path)

    def _override_defaults(self, config_path: Union[Path, str]) -> None:
        path = self._check_path(config_path)
        if not path:
            exit("Invalid config path '%s'" % config_path)
        try:
            with open(path) as f:
                config = yaml.safe_load(f)
                if not isinstance(config, Dict):
                    exit("Invalid config file given")
                self.channels = [Channel(**c) for c in config.pop("channels", [])]
                if log_level := config.get("log_level"):
                    self.log_level = self._choose_log_level(log_level)
                if log_file := config.get("log_file"):
                    self.log_file = Path(log_file)
                if log_fmt := config.get("log_fmt"):
                    self.log_fmt = log_fmt
                if feed_limit := config.get("feed_limit"):
                    self.feed_limit = feed_limit
                if channel_feed_limit := config.get("channel_feed_limit"):
                    self.channel_feed_limit = channel_feed_limit
                if storage_path := config.get("storage_path"):
                    self.storage_path = Path(storage_path)
        except Exception as e:
            exit("Can't parse config: %s" % e)

    def _check_path(self, path: Union[Path, str]) -> Optional[Path]:
        if isinstance(path, str):
            path = Path(expandvars(expanduser(path)))
        if path.parent.exists() and path.parent.is_dir():
            if path.suffix == ".yaml" or path.suffix == ".yml":
                return path

    def _choose_log_level(self, lvl: str) -> int:
        match lvl:
            case "debug" | "DEBUG":
                return logging.DEBUG
            case "info" | "INFO":
                return logging.INFO
            case "warning" | "WARNING":
                return logging.WARNING
            case "error" | "ERROR":
                return logging.ERROR
            case "none" | "None" | "NONE":
                return 0
        return 0
