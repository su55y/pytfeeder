import argparse
from typing import List

from pytfeeder.config import Config
from pytfeeder.feeder import Feeder
from pytfeeder.models import Entry


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
        highlight = []
        for i, channel in enumerate(self.feeder.channels):
            print(self.channels_fmt.format(title=channel.title, id=channel.channel_id))
            if channel.have_updates:
                highlight.append(str(i + self.offset))
        if highlight:
            print("\000active\037%s" % ",".join(highlight))

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
