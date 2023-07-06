import logging

from .config import Config
from . import dirs
from .feeder import Feeder
from .storage import Storage


def init_logger(config: Config):
    logger = logging.getLogger()
    logger.setLevel(config.log_level)
    handler = logging.FileHandler(config.log_file)
    handler.setFormatter(logging.Formatter(config.log_fmt))
    logger.addHandler(handler)


def init_feeder(config: Config):
    cache_dir = dirs.default_cachedir_path()
    if not cache_dir.exists():
        cache_dir.mkdir(parents=True)

    if config.log_level > 0:
        init_logger(config)

    db_file = config.storage_path or dirs.default_storage_path()
    return Feeder(config, Storage(db_file))
