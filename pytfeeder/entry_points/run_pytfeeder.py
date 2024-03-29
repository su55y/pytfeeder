import argparse
import asyncio
import logging

from pytfeeder.config import Config
from pytfeeder.defaults import default_config_path
from pytfeeder.feeder import Feeder
from pytfeeder.rofi import RofiPrinter
from pytfeeder.storage import Storage
from pytfeeder.consts import DEFAULT_ENTRY_FMT, DEFAULT_CHANNEL_FMT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--active-offset",
        type=int,
        default=1,
        metavar="INT",
        help="Index offset to mark entries as active (rofi)",
    )
    parser.add_argument(
        "-c",
        "--config-file",
        default=default_config_path(),
        metavar="PATH",
        help="Location of config file (default: %(default)s)",
    )
    parser.add_argument(
        "-i",
        "--channel-id",
        metavar="ID",
        help="Prints channel feed by given channel_id (rofi)",
    )
    parser.add_argument(
        "--channels-fmt",
        metavar="STR",
        help=f"Channels print format (default: {DEFAULT_CHANNEL_FMT!r}) (rofi)",
    )
    parser.add_argument(
        "--clean-cache",
        action="store_true",
        help="Deletes inactive channels and watched entries",
    )
    parser.add_argument(
        "--entries-fmt",
        metavar="STR",
        help=f"Entries print format (default: {DEFAULT_ENTRY_FMT!r} (rofi)",
    )
    parser.add_argument("-f", "--feed", action="store_true", help="Prints feed (rofi)")
    parser.add_argument(
        "-l", "--limit", type=int, metavar="INT", help="Use custom lines limit (rofi)"
    )
    parser.add_argument(
        "-p", "--print-config", action="store_true", help="Prints config"
    )
    parser.add_argument("-r", "--rofi", action="store_true", help="Rofi mode")
    parser.add_argument(
        "-s",
        "--sync",
        action="store_true",
        help="Updates all feeds and prints new entries count",
    )
    parser.add_argument(
        "--separator",
        default="\n",
        metavar="STR",
        help="Line separator (default: %(default)r) (rofi)",
    )
    parser.add_argument(
        "-u", "--unviewed", action="store_true", help="Prints unviewed entries count"
    )
    parser.add_argument(
        "-v",
        "--viewed",
        metavar="ID",
        help="Mark as viewed (Accepts entry/channel id or keyword 'all')",
    )

    return parser.parse_args()


def init_logger(config: Config):
    logger = logging.getLogger()
    logger.setLevel(config.log_level)
    handler = logging.FileHandler(config.log_file)
    handler.setFormatter(logging.Formatter(config.log_fmt))
    logger.addHandler(handler)


def run():
    args = parse_args()
    config = Config(args.config_file)
    if not config:
        exit(1)
    if args.print_config:
        print(config)
        exit(0)

    if not config.cache_dir.exists():
        config.cache_dir.mkdir(parents=True)

    if config.log_level > 0:
        init_logger(config)

    feeder = Feeder(config, Storage(config.storage_path))
    if args.clean_cache:
        feeder.clean_cache()

    if args.viewed:
        if args.viewed == "all":
            feeder.mark_as_viewed()
        elif len(args.viewed) == 24:
            feeder.mark_as_viewed(channel_id=args.viewed)
        elif len(args.viewed) == 11:
            feeder.mark_as_viewed(id=args.viewed)

    before_update = 0
    if args.sync:
        before_update = feeder.unviewed_count()
        asyncio.run(feeder.sync_entries())
        if not args.rofi:
            print(feeder.unviewed_count() - before_update)

    if args.rofi:
        printer = RofiPrinter(feeder=feeder, config=config, args=args)

        if args.clean_cache:
            printer.print_message("cache cleaned")
        if args.sync:
            if new_entries := (feeder.unviewed_count() - before_update):
                printer.print_message("%d new entries" % new_entries)
        if args.channel_id:
            printer.print_channel_feed(args.channel_id)
        elif args.feed:
            printer.print_feed()
        else:
            printer.print_channels()
    else:
        if args.unviewed:
            print(feeder.unviewed_count())
