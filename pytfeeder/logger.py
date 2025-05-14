from enum import IntEnum
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

from .utils import expand_path


class LogLevel(IntEnum):
    NOTSET = logging.NOTSET
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR


log_levels_map: dict[str, LogLevel] = {
    "debug": LogLevel.DEBUG,
    "info": LogLevel.INFO,
    "warning": LogLevel.WARNING,
    "error": LogLevel.ERROR,
}


@dataclass
class LoggerConfig:
    file: Path | None = None
    fmt: str | None = None
    level: LogLevel = LogLevel.NOTSET
    stream: bool = False

    def __post_init__(self) -> None:
        if self.file is not None:
            self.file = expand_path(self.file)

    def update(self, kwargs: dict[str, Any]) -> None:
        for k, v in kwargs.items():
            if k in vars(self) and v is not None:
                if k == "level":
                    v = log_levels_map.get(v.lower(), self.level)
                elif k == "file":
                    v = expand_path(v)
                setattr(self, k, v)

    def __repr__(self) -> str:
        repr_str = "logger:\n"
        for k, v in vars(self).items():
            if k == "level":
                v = v.name.lower()
            elif k == "fmt":
                v = repr(v)
            repr_str += f"  {k}: {v}\n"
        return repr_str


def init_logger(c: LoggerConfig) -> None:
    log = logging.getLogger()
    log.setLevel(c.level)

    h: logging.Handler = logging.NullHandler()
    if c.file:
        h = logging.FileHandler(c.file)
    elif c.stream:
        h = logging.StreamHandler()

    if c.fmt is not None:
        h.setFormatter(logging.Formatter(c.fmt))

    log.addHandler(h)
