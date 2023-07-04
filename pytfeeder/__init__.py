import logging

from .config import Config
from . import dirs
from .feeder import Feeder
from .storage import Storage


def init_logger(**kwargs):
    if not (file := kwargs.get("file")):
        return
    LOG_FMT = "[%(asctime)-.19s %(levelname)s] %(message)s (%(filename)s:%(lineno)d)"
    logger = logging.getLogger()
    logger.setLevel(kwargs.get("level", logging.INFO))
    handler = logging.FileHandler(file)
    handler.setFormatter(logging.Formatter(kwargs.get("format", LOG_FMT)))
    logger.addHandler(handler)


def init_feeder(config: Config):
    cache_dir = dirs.default_cachedir_path()
    if not cache_dir.exists():
        cache_dir.mkdir(parents=True)

    init_logger(
        file=config.log_file or dirs.default_logfile_path(),
        level=config.log_level,
    )

    db_file = config.storage_path or dirs.default_storage_path()
    return Feeder(config, Storage(db_file))
