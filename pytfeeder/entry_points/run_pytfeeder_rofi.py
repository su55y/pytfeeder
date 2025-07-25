import sys

from pytfeeder import Config, Feeder, Storage
from pytfeeder.logger import init_logger
from pytfeeder.models import Entry
from pytfeeder.rofi import args as rofi_args


def html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class RofiPrinter:
    def __init__(self, feeder: Feeder) -> None:
        self.feeder = feeder
        self.c = self.feeder.config.rofi
        if self.c.alphabetic_sort:
            self.feeder.channels_aplhabetic_sort()
        if self.c.unwatched_first:
            self.feeder.channels_unwatched_first_sort()

        self.__message_printed = False

    def print_channels(self) -> None:
        self.print_message("%d unwatched entries" % self.feeder.unwatched_count())
        print("\000data\037main", end=self.c.separator)

        if not self.c.hide_feed:
            total = self.feeder.total_entries_count(exclude_hidden=True)
            unwatched = self.feeder.unwatched_count()
            print(
                self.c.channels_fmt.format(
                    id="feed",
                    title="Feed",
                    total=total,
                    unwatched=unwatched,
                    active=["false", "true"][unwatched > 0],
                )
            )

        for channel in self.feeder.channels:
            if channel.entries_count == 0 and self.c.hide_empty:
                continue
            line = self.c.channels_fmt.format(
                id=channel.channel_id,
                title=html_escape(channel.title),
                total=channel.entries_count,
                unwatched=channel.unwatched_count,
                active=["false", "true"][channel.have_updates],
            )
            if channel.entries_count == 0:
                line += "\037nonselectable\037true"
            print(line, end=self.c.separator)

    def print_feed(self) -> None:
        print("\000data\037feed", end=self.c.separator)
        entries = self.feeder.feed(
            self.c.feed_limit, unwatched_first=self.c.unwatched_first
        )
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

        message = html_escape(self.feeder.channel_title(channel_id))
        if unwatched_count := self.feeder.unwatched_count(channel_id):
            message = f"{message}, {unwatched_count} unwatched entries"

        self.print_message(message)
        print("\000data\037%s" % channel_id, end=self.c.separator)

        if entries := self.feeder.channel_feed(
            channel_id,
            limit=self.c.channel_feed_limit,
            unwatched_first=self.c.unwatched_first,
        ):
            self.print_entries(entries, self.c.entries_fmt)

    def print_entries(self, entries: list[Entry], fmt: str) -> None:
        for entry in entries:
            channel_title = html_escape(self.feeder.channel_title(entry.channel_id))
            meta = channel_title
            if len(parts := meta.split()):
                meta += "%s%s" % (",".join(parts), "".join(parts))

            print(
                fmt.format(
                    title=html_escape(entry.title),
                    id=entry.id,
                    channel_title=channel_title,
                    meta=meta,
                    published=entry.published.strftime(self.c.datetime_fmt),
                    active=["true", "false"][entry.is_viewed],
                ),
                end=self.c.separator,
            )

    def print_tags(self) -> None:
        if len(self.feeder.tags_map) == 0:
            self.print_message("No tags")
            self.print_channels()
            return

        print("\000data\037tags", end=self.c.separator)
        self.print_message("TAGS")
        for tag in self.feeder.tags_map.values():
            if tag.entries_count == 0 and self.c.hide_empty:
                continue
            print(
                self.c.channels_fmt.format(
                    id=tag.title,
                    title=html_escape(tag.title),
                    total=tag.entries_count,
                    unwatched=tag.unwatched_count,
                    active=["false", "true"][tag.have_updates],
                ),
                end=self.c.separator,
            )

    def print_tag(self, tag: str) -> None:
        if not tag:
            self.print_error("Invalid tag ''")
            sys.exit(1)
        if tag not in self.feeder.tags_map:
            self.print_message(f"Unknown tag {tag!r}")
            sys.exit(0)
        if self.feeder.tags_map[tag].entries_count == 0:
            self.print_message(f"Tag {tag!r} is empty")
            sys.exit(0)
        t = self.feeder.tags_map[tag]
        print("\000data\037", end=self.c.separator)
        self.print_message(f"{tag} {t.unwatched_count}/{t.entries_count}")
        for c in t.channels:
            line = self.c.channels_fmt.format(
                id=c.channel_id,
                title=html_escape(c.title),
                total=c.entries_count,
                unwatched=c.unwatched_count,
                active=["false", "true"][c.have_updates],
            )
            if c.entries_count == 0:
                line += "\037nonselectable\037true"
            print(line, end=self.c.separator)

    def print_message(self, message: str) -> None:
        if not self.__message_printed:
            print("\000message\037%s" % message, end=self.c.separator)
        self.__message_printed = True

    def print_error(self, message: str) -> None:
        if not self.__message_printed:
            self.print_message(message)
            # FIXME: should not print if already printed anything
            print(" ", end=self.c.separator)
        else:
            print(message, end=self.c.separator)


def print_error(message: str):
    print(f"\000message\037{message}\n \n")


def main():
    try:
        wrapped_main()
    except Exception as e:
        print_error(f"ERR: {e!s}")
        sys.exit(1)


def wrapped_main():
    global print_error

    args = rofi_args.parse_args()
    config = Config(config_file=args.config_file)
    config.rofi.update(vars(args))

    if not config.storage_path.exists():
        config.storage_path.mkdir(parents=True)

    init_logger(config.logger)

    feeder = Feeder(config, Storage(config.storage_path))
    if args.watched:
        if args.watched == "all":
            feeder.mark_as_watched()
        elif len(args.watched) == 24:
            feeder.mark_as_watched(channel_id=args.watched)
        elif len(args.watched) == 11:
            feeder.mark_as_watched(id=args.watched)

    printer = RofiPrinter(feeder=feeder)
    print_error = printer.print_error

    if args.sync:
        import asyncio

        new, err = asyncio.run(feeder.sync_entries())
        if err:
            printer.print_error(f"ERR: {err}")
        elif new > 0:
            printer.print_message(f"{new} new entries")
        else:
            printer.print_message("No updates")

    if args.channel_id:
        printer.print_channel_feed(args.channel_id)
    elif args.feed:
        printer.print_feed()
    elif args.tags:
        printer.print_tags()
    elif args.tag:
        printer.print_tag(args.tag)
    else:
        printer.print_channels()


if __name__ == "__main__":
    main()
