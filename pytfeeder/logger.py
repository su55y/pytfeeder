from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

from .utils import expand_path

log_levels_map = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


@dataclass
class LoggerConfig:
    file: Path | None = None
    fmt: str | None = None
    level: int = logging.NOTSET
    stream: bool = False

    def __post_init__(self) -> None:
        if self.file is not None:
            self.file = expand_path(self.file)

    def update(self, kwargs: dict[str, Any]) -> None:
        for k, v in kwargs.items():
            if k in vars(self) and v is not None:
                if k == "level":
                    v = self._choose_log_level_by_name(v)
                elif k == "file":
                    v = expand_path(v)
                setattr(self, k, v)

    def _choose_log_level_by_name(self, name: str) -> int:
        return log_levels_map.get(name.lower(), self.level)

    def __repr__(self) -> str:
        repr_str = "logger:\n"
        level_name = {v: k for k, v in log_levels_map.items()}.get(self.level)
        for k, v in vars(self).items():
            if k == "level":
                v = level_name
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
