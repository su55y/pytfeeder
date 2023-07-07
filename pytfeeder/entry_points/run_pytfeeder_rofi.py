import argparse
import asyncio
from typing import List

from pytfeeder.config import Config
import pytfeeder.dirs as dirs
from pytfeeder.feeder import Feeder
from pytfeeder.models import Entry
from pytfeeder import init_feeder


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
        "-s",
        "--sync",
        action="store_true",
        help="Updates all feeds and prints message with new entries count",
    )
    parser.add_argument(
        "-v",
        "--viewed",
        metavar="ID",
        help="Mark as viewed (Accepts entry/channel id or keyword 'all')",
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
        print("\000message\037%d unviewed entries" % self.feeder.unviewed_count())
        print("\000data\037main")
        print("common feed\000info\037feed")
        for channel in self.feeder.channels:
            print(self.channels_fmt.format(title=channel.title, id=channel.channel_id))

    def print_common_feed(self) -> None:
        print("\000data\037common_feed")
        self._print_entries(
            self.feeder.common_feed(self.limit or self.config.common_feed_limit)
        )

    def print_channel_feed(self, channel_id: str) -> None:
        if len(channel_id) != 24:
            exit("invalid channel_id")

        print("\000message\037%s" % self._channel_feed_message(channel_id))
        print("\000data\037%s" % channel_id)
        self._print_entries(
            self.feeder.channel_feed(
                channel_id, self.limit or self.config.channel_feed_limit
            )
        )

    def _channel_feed_message(self, channel_id: str) -> str:
        message = ""
        if filtered_channels := [
            c for c in self.config.channels if c.channel_id == channel_id
        ]:
            message = filtered_channels.pop().title
        if unviewed_count := self.feeder.unviewed_count(channel_id):
            unviewed = "%d unviewed entries" % unviewed_count
            message = f"{message}, {unviewed}" if message else unviewed
        return message

    def _print_entries(self, entries: List[Entry]) -> None:
        if not entries:
            print("\000message\037no entries")
            return
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

    feeder = init_feeder(config)
    if args.clean_cache:
        feeder.clean_cache()
        print("\000message\037cache cleaned")
    if args.sync:
        before_update = feeder.unviewed_count()
        asyncio.run(feeder.sync_entries())
        print(
            "\000message\037%d new entries" % (feeder.unviewed_count() - before_update)
        )
    if args.viewed:
        if args.viewed == "all":
            feeder.mark_as_viewed()
        elif len(args.viewed) == 24:
            feeder.mark_as_viewed(channel_id=args.viewed)
        elif len(args.viewed) == 11:
            feeder.mark_as_viewed(id=args.viewed)

    printer = RofiPrinter(feeder=feeder, config=config, args=args)
    if args.channel_id:
        printer.print_channel_feed(args.channel_id)
    elif args.feed:
        printer.print_common_feed()
    else:
        printer.print_channels()
