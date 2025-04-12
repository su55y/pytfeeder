import logging
from pathlib import Path
import os

from pytfeeder.logger import init_logger, LoggerConfig


def setup_logging(
    filename: str,
    fmt: str = "[%(levelname)s] %(message)s %(filename)s:%(lineno)d",
    level: int = logging.DEBUG,
) -> None:
    dir = os.environ.get("PYTFEEDER_TESTLOG_DIR")
    if not dir:
        return
    dirpath = Path(dir)
    if not dirpath.is_dir():
        return

    init_logger(LoggerConfig(file=dirpath / filename, fmt=fmt, level=level))
