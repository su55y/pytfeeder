from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union
from os.path import expandvars

import yaml

from .defaults import default_cachedir_path
from .models import Channel


LOG_FMT = "[%(asctime)-.19s %(levelname)s] %(message)s (%(filename)s:%(lineno)d)"

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
    storage_path: Path
    log_level: int
    log_file: Path
    log_fmt: str
    unviewed_first: bool
    feed_limit: Optional[int] = None
    channel_feed_limit: Optional[int] = None

    def __init__(
        self,
        config_file: Optional[Union[Path, str]] = None,
        channels: Optional[List[Channel]] = None,
        feed_limit: Optional[int] = None,
        channel_feed_limit: Optional[int] = None,
        cache_dir: Optional[Path] = None,
        log_level: Optional[int] = None,
        log_file: Optional[Path] = None,
        log_fmt: Optional[str] = None,
        storage_path: Optional[Path] = None,
        unviewed_first: Optional[bool] = None,
    ) -> None:
        self.channels = channels or []
        self.feed_limit = feed_limit
        self.channel_feed_limit = channel_feed_limit
        self.cache_dir = cache_dir or default_cachedir_path()
        self.log_level = log_level or logging.NOTSET
        self.log_file = log_file or self.cache_dir.joinpath("pytfeeder.log")
        self.log_fmt = log_fmt or LOG_FMT
        self.storage_path = storage_path or self.cache_dir.joinpath("pytfeeder.db")
        self.unviewed_first = unviewed_first or False
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
        if unviewed_first := config.get("unviewed_first"):
            self.unviewed_first = bool(unviewed_first)

    def __repr__(self) -> str:
        repr_str = ""
        repr_str += f"cache_dir: {self.cache_dir!s}\n"
        if self.channels:
            repr_str += "channels:\n"
            repr_str += "".join(
                f"  - {{ channel_id: {c.channel_id}, title: {c.title!r} }}\n"
                for c in self.channels
            )
        repr_str += f"channel_feed_limit: {self.channel_feed_limit}\n"
        repr_str += f"feed_limit: {self.feed_limit}\n"
        repr_str += f"log_fmt: {self.log_fmt!r}\n"
        repr_str += f"log_level: {self.log_level}\n"
        repr_str += f"unviewed_first: {self.unviewed_first}\n"
        return repr_str.strip()
