import logging
from pathlib import Path
import os
import tempfile

from pytfeeder.logger import init_logger, LoggerConfig, LogLevel


def setup_logging(
    filename: str,
    fmt: str = "[%(levelname)s] %(message)s %(filename)s:%(lineno)d",
    level: int = logging.DEBUG,
) -> None:
    dir = os.environ.get("PYTFEEDER_TESTLOG_DIR")
    if not dir:
        init_logger(LoggerConfig())
        return
    dirpath = Path(dir)
    if not dirpath.is_dir():
        init_logger(LoggerConfig())
        return

    level_ = LogLevel(level) if level in LogLevel else LogLevel.DEBUG
    init_logger(LoggerConfig(file=dirpath / filename, fmt=fmt, level=level_))


def temp_storage_path() -> Path:
    test_storage = tempfile.NamedTemporaryFile(
        suffix=".db",
        prefix="test_storage",
        delete_on_close=False,
    )
    test_storage.close()
    return Path(test_storage.name)
