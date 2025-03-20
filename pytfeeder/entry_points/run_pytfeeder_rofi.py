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
        self.__message_printed = False

    def print_channels(self) -> None:
        self.print_message("%d unwatched entries" % self.feeder.unwatched_count())
        print("\000data\037main", end=self.c.separator)
        unwatched_count = lambda _: 0
        if "{unwatched_count}" in self.c.channels_fmt:
            unwatched_count = lambda channel_id: self.feeder.unwatched_count(channel_id)
        for channel in self.feeder.channels:
            print(
                self.c.channels_fmt.format(
                    id=channel.channel_id,
                    title=channel.title,
                    unwatched_count=unwatched_count(channel.channel_id),
                    active=["false", "true"][channel.have_updates],
                ),
                end=self.c.separator,
            )

    def print_feed(self) -> None:
        print("\000data\037feed", end=self.c.separator)
        entries = self.feeder.feed(self.c.feed_limit)
        if not entries:
            self.print_message("no entries")
            return
        unwatched = [e for e in entries if not e.is_viewed]
        if len(unwatched):
            message = "feed, %d new entries of %d" % (len(unwatched), len(entries))
        else:
            message = "feed, %d entries" % len(entries)
        self.print_message(message)
        self.print_entries(entries, self.c.feed_entries_fmt)

    def print_channel_feed(self, channel_id: str) -> None:
        if len(channel_id) != 24:
            self.print_message("invalid channel_id")
            return

        message = self.feeder.channel_title(channel_id)
        if unwatched_count := self.feeder.unwatched_count(channel_id):
            message = f"{message}, {unwatched_count} unwatched entries"

        self.print_message(message)
        print("\000data\037%s" % channel_id, end=self.c.separator)

        if entries := self.feeder.channel_feed(channel_id, self.c.channel_feed_limit):
            self.print_entries(entries, self.c.entries_fmt)

    def print_entries(self, entries: List[Entry], fmt: str) -> None:
        for entry in entries:
            channel_title = self.feeder.channel_title(entry.channel_id)
            meta = channel_title
            if len(parts := meta.split()):
                meta += "%s%s" % (",".join(parts), "".join(parts))

            print(
                fmt.format(
                    title=entry.title.replace("&", "&amp;"),
                    id=entry.id,
                    channel_title=channel_title,
                    meta=meta,
                    published=entry.published.strftime(self.c.datetime_fmt),
                    active=["true", "false"][entry.is_viewed],
                ),
                end=self.c.separator,
            )

    def print_message(self, message: str) -> None:
        if not self.__message_printed:
            print("\000message\037%s" % message, end=self.c.separator)
        self.__message_printed = True


def main():
    args = parse_args()
    config = Config(config_file=args.config_file)
    if not config:
        exit(1)

    config.rofi.update(vars(args))

    if not config.storage_path.exists():
        config.storage_path.mkdir(parents=True)

    feeder = Feeder(config, Storage(config.storage_path))
    if args.watched:
        if args.watched == "all":
            feeder.mark_as_watched()
        elif len(args.watched) == 24:
            feeder.mark_as_watched(channel_id=args.watched)
        elif len(args.watched) == 11:
            feeder.mark_as_watched(id=args.watched)

    before_update = 0
    if args.sync:
        import asyncio

        before_update = feeder.unwatched_count()
        asyncio.run(feeder.sync_entries())

    printer = RofiPrinter(feeder=feeder)

    if args.sync:
        if new_entries := (feeder.unwatched_count() - before_update):
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
