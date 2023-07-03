import argparse
import asyncio
from typing import List

from pytfeeder.config import Config
import pytfeeder.dirs as dirs
from pytfeeder.feeder import Feeder
from pytfeeder.models import Entry
from pytfeeder.storage import Storage
from .run_pytfeeder import init_logger


def parse_args() -> argparse.Namespace:
    DEFAULT_FMT = "{title}\000info\037{id}"
    parser = argparse.ArgumentParser(description="package: %s" % __package__)
    parser.add_argument(
        "-c",
        "--config-file",
        default=dirs.default_config_path(),
        metavar="PATH",
        help="Location of config file (default: %(default)s)",
    )
    parser.add_argument(
        "--channels-fmt",
        default=DEFAULT_FMT,
        metavar="STR",
        help=r"Channels print format (default: '{title}\000info\037{id}')",
    )
    parser.add_argument(
        "--clean-cache",
        action="store_true",
        help="Deletes inactive channels and watched entries",
    )
    parser.add_argument(
        "--entries-fmt",
        default=DEFAULT_FMT,
        metavar="STR",
        help=r"Entries print format (default: '{title}\000info\037{id}')",
    )
    parser.add_argument(
        "-i",
        "--channel-id",
        metavar="ID",
        help="Prints channel feed by given channel_id",
    )
    parser.add_argument("-f", "--feed", action="store_true", help="Prints common feed")
    parser.add_argument(
        "-l", "--limit", type=int, metavar="INT", help="Use custom lines limit"
    )
    parser.add_argument(
        "-s", "--sync", action="store_true", help="Just update feeds and exit"
    )

    return parser.parse_args()


class RofiPrinter:
    def __init__(
        self, feeder: Feeder, config: Config, args: argparse.Namespace
    ) -> None:
        self.config = config
        self.feeder = feeder
        self.channels_fmt = args.channels_fmt
        self.entries_fmt = args.entries_fmt
        self.limit = args.limit

    def print_channels(self) -> None:
        for channel in self.feeder.channels:
            print(self.channels_fmt.format(title=channel.title, id=channel.channel_id))

    def print_common_feed(self) -> None:
        self._print_entries(
            self.feeder.common_feed(self.limit or self.config.common_feed_limit)
        )

    def print_channel_feed(self, channel_id: str) -> None:
        if len(channel_id) != 24:
            exit("invalid channel_id")
        self._print_entries(
            self.feeder.channel_feed(
                channel_id, self.limit or self.config.channel_feed_limit
            )
        )

    def _print_entries(self, entries: List[Entry]):
        if not entries:
            print("\000message\037no entries")
        highlight = []
        for i, entry in enumerate(entries):
            if not entry.is_viewed:
                highlight.append(str(i + 1))
            print(self.entries_fmt.format(title=entry.title, id=entry.id))

        if highlight:
            print("\000active\037%s" % ",".join(highlight))


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
        print("\000message\037cache cleaned")
    if args.sync:
        asyncio.run(feeder.sync_entries())
        print("\000message\037feeds synced")
    printer = RofiPrinter(feeder=feeder, config=config, args=args)
    if args.channel_id:
        printer.print_channel_feed(args.channel_id)
    elif args.feed:
        printer.print_common_feed()
    else:
        print("common feed\000info\037feed")
        printer.print_channels()
