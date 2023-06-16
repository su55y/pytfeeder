from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Dict, List, Optional
from os.path import expanduser, expandvars

import yaml

from .models import Channel


@dataclass
class Config:
    channels: List[Channel]
    common_feed_limit: Optional[int] = None
    channel_feed_limit: Optional[int] = None
    log_level: Optional[int] = None
    log_file: Optional[Path] = None
    storage_path: Optional[Path] = None

    def __init__(self, path_str: str) -> None:
        path = self._check_path(path_str)
        try:
            with open(path) as f:
                config = yaml.safe_load(f)
                if not isinstance(config, Dict):
                    raise Exception("invalid config")
                self.channels = [Channel(**c) for c in config.pop("channels", [])]
                if log_level := config.get("log_level"):
                    self.log_level = self._choose_log_level(log_level)
                if log_file := config.get("log_file"):
                    self.log_file = Path(log_file)
                if common_feed_limit := config.get("common_feed_limit"):
                    self.common_feed_limit = common_feed_limit
                if channel_feed_limit := config.get("channel_feed_limit"):
                    self.channel_feed_limit = channel_feed_limit
                if storage_path := config.get("storage_path"):
                    self.storage_path = Path(storage_path)
        except Exception as e:
            exit(str(e))

    def _check_path(self, path_str) -> Path:
        path = Path(expandvars(expanduser(path_str)))
        if not path.parent.exists() or not path.parent.is_dir():
            exit(f"{path.parent} not exists or not a directory")
        elif path.suffix == ".yaml" or path.suffix == ".yml":
            return path
        else:
            exit(f"invalid config path '{path}'")

    def _choose_log_level(self, lvl: str) -> Optional[int]:
        match lvl:
            case "debug" | "DEBUG":
                return logging.DEBUG
            case "info" | "INFO":
                return logging.INFO
