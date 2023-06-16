import logging
import sys

import asyncio
from typing import List

from pytfeeder.args import parse_args
from pytfeeder.config import Config
from pytfeeder.feeder import Feeder
from pytfeeder.models import Entry, Channel
from pytfeeder.storage import Storage, DBHooks


def init_logger(file="/tmp/pyt-feed.log", level=logging.INFO, format=None):
    LOG_FMT = "[%(asctime)-.19s %(levelname)s] %(message)s (%(funcName)s:%(lineno)d)"
    logger = logging.getLogger()
    logger.setLevel(level)
    handler = logging.FileHandler(file)
    handler.setFormatter(logging.Formatter(format or LOG_FMT))
    logger.addHandler(handler)


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
