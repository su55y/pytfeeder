import argparse
import asyncio
import logging
import sys
from typing import List

from pytfeeder.config import Config
import pytfeeder.dirs as dirs
from pytfeeder.feeder import Feeder
from pytfeeder.models import Entry, Channel
from pytfeeder.storage import Storage, DBHooks


def init_logger(**kwargs):
    if not (file := kwargs.get("file")):
        return
    LOG_FMT = "[%(asctime)-.19s %(levelname)s] %(message)s (%(funcName)s:%(lineno)d)"
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
        help="Location of config file (default: %(default)s)",
    )
    parser.add_argument(
        "-d",
        "--cache-dir",
        default=dirs.default_cachedir_path(),
        help="Location of cache directory (default: %(default)s)",
    )
    parser.add_argument(
        "-l",
        "--log-file",
        default=dirs.default_logfile_path(),
        help="Location of log file (default: %(default)s)",
    )
    parser.add_argument("-i", "--channel-id", help="print channel feed")
    parser.add_argument("-s", "--sync", action="store_true", help="just update feeds")
    parser.add_argument("-f", "--feed", action="store_true", help="common feed")

    return parser.parse_args()


def print_entries(entries: List[Entry]):
    highlight = []
    for i, e in enumerate(entries):
        if not e.is_viewed:
            highlight.append(str(i + 1))
        print("%s\000info\037%s" % (e.title, e.id))

    print("\000active\037%s" % ",".join(highlight))


def print_channels(channels: List[Channel]):
    for c in channels:
        sys.stdout.write("%s\000info\037%s\n" % (c.title, c.channel_id))


def run():
    args = parse_args()
    config = Config(args.config_file)
    if not config:
        exit(1)

    if not args.cache_dir.exists():
        args.cache_dir.mkdir(parents=True)

    logger_opts = {"file": args.log_file or config.log_file}
    if config.log_level is not None:
        logger_opts["level"] = config.log_level
    init_logger(**logger_opts)

    db_file = args.cache_dir.joinpath("test.db")
    if err := DBHooks(db_file).init_db():
        exit(repr(err))

    feeder = Feeder(config, Storage(db_file))
    if args.sync:
        feeder.sync_channels()
        asyncio.run(feeder.sync_entries())
        exit(0)
    if args.channel_id:
        print_entries(feeder.channel_feed(args.channel_id))
    elif args.feed:
        print_entries(feeder.common_feed())
    else:
        print_channels(feeder.channels)
