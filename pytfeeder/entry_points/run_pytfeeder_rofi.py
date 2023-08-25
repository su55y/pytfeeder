import argparse
import asyncio
from typing import List

from pytfeeder.config import Config
from pytfeeder.defaults import default_config_path
from pytfeeder.feeder import Feeder
from pytfeeder.models import Entry
from pytfeeder import init_feeder

DEFAULT_CHANNEL_FMT = "{title}\000info\037{id}"
DEFAULT_ENTRY_FMT = "{title}\000info\037{id}\037meta\037{channel_title}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config-file",
        default=default_config_path(),
        metavar="PATH",
        help="Location of config file (default: %(default)s)",
    )
    parser.add_argument(
        "--channels-fmt",
        default=DEFAULT_CHANNEL_FMT,
        metavar="STR",
        help=r"Channels print format (default: %(default)r)",
    )
    parser.add_argument(
        "--clean-cache",
        action="store_true",
        help="Deletes inactive channels and watched entries",
    )
    parser.add_argument(
        "--entries-fmt",
        default=DEFAULT_ENTRY_FMT,
        metavar="STR",
        help=r"Entries print format (default: %(default)r",
    )
    parser.add_argument(
        "-i",
        "--channel-id",
        metavar="ID",
        help="Prints channel feed by given channel_id",
    )
    parser.add_argument("-f", "--feed", action="store_true", help="Prints feed")
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
    parser.add_argument(
        "--active-offset",
        type=int,
        default=1,
        help="index offset to mark entries as active",
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
        self.offset = args.active_offset

    def print_channels(self) -> None:
        self.print_message("%d unviewed entries" % self.feeder.unviewed_count())
        print("\000data\037main")
        for channel in self.feeder.channels:
            print(self.channels_fmt.format(title=channel.title, id=channel.channel_id))

    def print_feed(self) -> None:
        print("\000data\037feed")
        entries = self.feeder.feed(self.limit or self.config.feed_limit)
        if not entries:
            self.print_message("no entries")
            return
        unviewed = [e for e in entries if not e.is_viewed]
        if len(unviewed):
            message = "feed, %d new entries of %d" % (len(unviewed), len(entries))
        else:
            message = "feed, %d entries" % len(entries)
        self.print_message(message)
        self.print_entries(entries)

    def print_channel_feed(self, channel_id: str) -> None:
        if len(channel_id) != 24:
            self.print_message("invalid channel_id")
            return

        message = self.feeder.channel_title(channel_id)
        if unviewed_count := self.feeder.unviewed_count(channel_id):
            message = f"{message}, {unviewed_count} unviewed entries"

        self.print_message(message)
        print("\000data\037%s" % channel_id)

        if entries := self.feeder.channel_feed(
            channel_id, self.limit or self.config.channel_feed_limit
        ):
            self.print_entries(entries)

    def print_entries(self, entries: List[Entry]) -> None:
        highlight = []
        for i, entry in enumerate(entries):
            if not entry.is_viewed:
                highlight.append(str(i + self.offset))

            meta = self.feeder.channel_title(entry.channel_id)
            if len(parts := meta.split()):
                meta += "%s%s" % (",".join(parts), "".join(parts))

            print(
                self.entries_fmt.format(
                    title=entry.title, id=entry.id, channel_title=meta
                )
            )

        if highlight:
            print("\000active\037%s" % ",".join(highlight))

    def print_message(self, message: str) -> None:
        print("\000message\037%s" % message)


def run():
    args = parse_args()

    config = Config(args.config_file)
    if not config:
        exit(1)

    feeder = init_feeder(config)
    printer = RofiPrinter(feeder=feeder, config=config, args=args)

    if args.clean_cache:
        feeder.clean_cache()
        printer.print_message("cache cleaned")

    if args.sync:
        before_update = feeder.unviewed_count()
        asyncio.run(feeder.sync_entries())
        if new_entries := (feeder.unviewed_count() - before_update):
            printer.print_message("%d new entries" % new_entries)

    if args.viewed:
        if args.viewed == "all":
            feeder.mark_as_viewed()
        elif len(args.viewed) == 24:
            feeder.mark_as_viewed(channel_id=args.viewed)
        elif len(args.viewed) == 11:
            feeder.mark_as_viewed(id=args.viewed)

    if args.channel_id:
        printer.print_channel_feed(args.channel_id)
    elif args.feed:
        printer.print_feed()
    else:
        printer.print_channels()
