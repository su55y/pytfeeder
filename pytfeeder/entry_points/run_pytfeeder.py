import argparse
import asyncio
import logging

from pytfeeder.config import Config
import pytfeeder.dirs as dirs
from pytfeeder.feeder import Feeder
from pytfeeder.storage import Storage


def init_logger(**kwargs):
    if not (file := kwargs.get("file")):
        return
    LOG_FMT = "[%(asctime)-.19s %(levelname)s] %(message)s (%(filename)s:%(lineno)d)"
    logger = logging.getLogger()
    logger.setLevel(kwargs.get("level", logging.INFO))
    handler = logging.FileHandler(file)
    handler.setFormatter(logging.Formatter(kwargs.get("format", LOG_FMT)))
    logger.addHandler(handler)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="package: %s" % __package__)
    parser.add_argument(
        "-c",
        "--config-file",
        default=dirs.default_config_path(),
        metavar="PATH",
        help="Location of config file (default: %(default)s)",
    )
    parser.add_argument(
        "--clean-cache",
        action="store_true",
        help="Deletes inactive channels and watched entries",
    )
    parser.add_argument(
        "-s", "--sync", action="store_true", help="Just update feeds and exit"
    )

    return parser.parse_args()


def run():
    args = parse_args()
    config = Config(args.config_file)
    if not config:
        exit(1)

    cache_dir = dirs.default_cachedir_path()
    if not cache_dir.exists():
        cache_dir.mkdir(parents=True)

    init_logger(
        file=config.log_file or dirs.default_logfile_path(),
        level=config.log_level,
    )

    db_file = config.storage_path or dirs.default_storage_path()
    feeder = Feeder(config, Storage(db_file))
    if args.clean_cache:
        feeder.clean_cache()
    if args.sync:
        asyncio.run(feeder.sync_entries())
