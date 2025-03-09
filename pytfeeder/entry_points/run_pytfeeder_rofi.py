from typing import List

from pytfeeder.config import Config
from pytfeeder.feeder import Feeder
from pytfeeder.models import Entry
from pytfeeder.storage import Storage
from pytfeeder.rofi.args import parse_args


class RofiPrinter:
    def __init__(self, feeder: Feeder) -> None:
        self.feeder = feeder
        self.c = self.feeder.config.rofi
        if self.c.alphabetic_sort:
            self.feeder.channels.sort(key=lambda c: c.title)

    def print_channels(self) -> None:
        self.print_message("%d unviewed entries" % self.feeder.unviewed_count())
        print("\000data\037main", end=self.c.separator)
        highlight = []
        unviewed_count = lambda _: 0
        if "{unviewed_count}" in self.c.channels_fmt:
            unviewed_count = lambda channel_id: self.feeder.unviewed_count(channel_id)
        for i, channel in enumerate(self.feeder.channels):
            print(
                self.c.channels_fmt.format(
                    id=channel.channel_id,
                    title=channel.title,
                    unviewed_count=unviewed_count(channel.channel_id),
                ),
                end=self.c.separator,
            )
            if channel.have_updates:
                highlight.append(str(i + self.c.offset))
        if highlight:
            print("\000active\037%s" % ",".join(highlight), end=self.c.separator)

    def print_feed(self) -> None:
        print("\000data\037feed", end=self.c.separator)
        entries = self.feeder.feed(self.c.feed_limit)
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
        print("\000data\037%s" % channel_id, end=self.c.separator)

        if entries := self.feeder.channel_feed(channel_id, self.c.channel_feed_limit):
            self.print_entries(entries)

    def print_entries(self, entries: List[Entry]) -> None:
        highlight = []
        for i, entry in enumerate(entries):
            if not entry.is_viewed:
                highlight.append(str(i + self.c.offset))

            channel_title = self.feeder.channel_title(entry.channel_id)
            meta = channel_title
            if len(parts := meta.split()):
                meta += "%s%s" % (",".join(parts), "".join(parts))

            print(
                self.c.entries_fmt.format(
                    title=entry.title.replace("&", "&amp;"),
                    id=entry.id,
                    channel_title=channel_title,
                    meta=meta,
                    updated=entry.updated.strftime(self.c.datetime_fmt),
                ),
                end=self.c.separator,
            )

        if highlight:
            print("\000active\037%s" % ",".join(highlight), end=self.c.separator)

    def print_message(self, message: str) -> None:
        print("\000message\037%s" % message, end=self.c.separator)


def main():
    args = parse_args()
    config = Config(config_file=args.config_file)
    if not config:
        exit(1)

    config.rofi.update(vars(args))

    if not config.cache_dir.exists():
        config.cache_dir.mkdir(parents=True)

    feeder = Feeder(config, Storage(config.storage_path))
    if args.viewed:
        if args.viewed == "all":
            feeder.mark_as_viewed()
        elif len(args.viewed) == 24:
            feeder.mark_as_viewed(channel_id=args.viewed)
        elif len(args.viewed) == 11:
            feeder.mark_as_viewed(id=args.viewed)

    before_update = 0
    if args.sync:
        import asyncio

        before_update = feeder.unviewed_count()
        asyncio.run(feeder.sync_entries())

    printer = RofiPrinter(feeder=feeder)

    if args.sync:
        # TODO: change messages to notifications
        if new_entries := (feeder.unviewed_count() - before_update):
            printer.print_message("%d new entries" % new_entries)
        else:
            printer.print_message("no updates")

    if args.channel_id:
        printer.print_channel_feed(args.channel_id)
    elif args.feed:
        printer.print_feed()
    else:
        printer.print_channels()


if __name__ == "__main__":
    main()
