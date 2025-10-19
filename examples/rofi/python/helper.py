#!/usr/bin/env -S python3 -u

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

import yaml

from pytfeeder import Config, Feeder, Storage
from pytfeeder.defaults import default_config_path
from pytfeeder.logger import init_logger
from pytfeeder.models import Entry


def html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


DEFAULT_CHANNEL_FEED_LIMIT = -1
DEFAULT_FEED_LIMIT = -1
DEFAULT_CHANNELS_FMT = "{title}\000info\037{id}\037active\037{active}"
DEFAULT_ENTRIES_FMT = "{title}\000info\037{id}\037active\037{active}"
DEFAULT_DATETIME_FMT = "%b %d"
DEFAULT_SEPARATOR = "\n"


class Separator(str):
    pass


@dataclass
class RofiConfig:
    alphabetic_sort: bool = False
    channel_feed_limit: int = DEFAULT_CHANNEL_FEED_LIMIT
    channels_fmt: str = DEFAULT_CHANNELS_FMT
    feed_entries_fmt: str = DEFAULT_ENTRIES_FMT
    datetime_fmt: str = DEFAULT_DATETIME_FMT
    entries_fmt: str = DEFAULT_ENTRIES_FMT
    feed_limit: int = DEFAULT_FEED_LIMIT
    hide_empty: bool = False
    hide_feed: bool = False
    separator: Separator = Separator(DEFAULT_SEPARATOR)
    unwatched_first: bool = False

    def update(self, kwargs: dict[str, Any]) -> None:
        for k, v in kwargs.items():
            if k in vars(self) and v is not None:
                if isinstance(v, bool):
                    v = getattr(self, k, v) | v
                elif k == "separator":
                    v = Separator(v)
                setattr(self, k, v)

    def load(self, file: Path) -> None:
        if not file.exists():
            return
        with open(file) as f:
            d = yaml.safe_load(f)
        if not isinstance(d, dict):
            return
        if alphabetic_sort := d.get("alphabetic_sort", self.alphabetic_sort):
            self.alphabetic_sort = alphabetic_sort
        if channel_feed_limit := d.get("channel_feed_limit", -1):
            self.channel_feed_limit = channel_feed_limit
        if channels_fmt := d.get("channels_fmt"):
            self.channels_fmt = channels_fmt
        if feed_entries_fmt := d.get("feed_entries_fmt"):
            self.feed_entries_fmt = feed_entries_fmt
        if datetime_fmt := d.get("datetime_fmt"):
            self.datetime_fmt = datetime_fmt
        if entries_fmt := d.get("entries_fmt"):
            self.entries_fmt = entries_fmt
        if feed_limit := d.get("feed_limit", -1):
            self.feed_limit = feed_limit
        if hide_empty := d.get("hide_empty", False):
            self.hide_empty = hide_empty
        if v := d.get("separator"):
            self.separator = Separator(v)
        if unwatched_first := d.get("unwatched_first", False):
            self.unwatched_first = unwatched_first

    def __repr__(self) -> str:
        return "\n".join(f"{k}: {v!r}" for k, v in sorted(vars(self).items()))


class RofiPrinter:
    def __init__(self, feeder: Feeder, rofi_config: RofiConfig) -> None:
        self.feeder = feeder
        self.c: RofiConfig = rofi_config
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
            print(
                fmt.format(
                    title=html_escape(entry.title),
                    id=entry.id,
                    channel_title=channel_title,
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


def parse_args() -> argparse.Namespace:
    return create_parser().parse_args()


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-A",
        "--alphabetic-sort",
        action="store_true",
        help="Sort channels in alphabetic order, instead of order by config",
    )
    parser.add_argument(
        "-c",
        "--config",
        metavar="PATH",
        default=default_config_path(),
        type=Path,
        help="Config file path (default: %(default)s)",
    )
    parser.add_argument(
        "-C",
        "--rofi-config",
        metavar="PATH",
        default=default_config_path().with_name("rofi_config.yaml"),
        type=Path,
        help="Rofi config file path (default: %(default)s)",
    )
    parser.add_argument(
        "-l",
        "--channel-feed-limit",
        type=int,
        metavar="INT",
        help=f"Channels feed limit. Overrides config value (default: {DEFAULT_CHANNEL_FEED_LIMIT})",
    )
    parser.add_argument(
        "-i",
        "--channel-id",
        metavar="ID",
        help="Prints channel feed by given channel_id",
    )
    parser.add_argument(
        "--channels-fmt",
        type=lambda s: eval("'%s'" % s),
        metavar="STR",
        help=f"Channels print format (default: {DEFAULT_CHANNELS_FMT!r})",
    )
    parser.add_argument(
        "--datetime-fmt",
        metavar="STR",
        help=f"Datetime key format (default: {DEFAULT_DATETIME_FMT.replace('%', '%%')!r})",
    )
    parser.add_argument(
        "--entries-fmt",
        type=lambda s: eval("'%s'" % s),
        metavar="STR",
        help=f"Entries print format (default: {DEFAULT_ENTRIES_FMT!r}",
    )
    parser.add_argument("-f", "--feed", action="store_true", help="Prints feed")
    parser.add_argument(
        "--feed-entries-fmt",
        type=lambda s: eval("'%s'" % s),
        metavar="STR",
        help=f"Feed entries format (default: {DEFAULT_ENTRIES_FMT!r})",
    )
    parser.add_argument(
        "-L",
        "--feed-limit",
        type=int,
        metavar="INT",
        help=f"Feed limit. Overrides config value (default: {DEFAULT_FEED_LIMIT})",
    )
    parser.add_argument(
        "--hide-feed", action="store_true", help="Hide 'Feed' in channels list"
    )
    parser.add_argument(
        "--separator",
        type=lambda s: eval("'%s'" % s),
        metavar="STR",
        help="Line separator (default: %(default)r)",
    )
    parser.add_argument(
        "-s",
        "--sync",
        action="store_true",
        help="Updates all feeds and prints new entries count",
    )
    parser.add_argument("-t", "--tag", help="Print tag's channels")
    parser.add_argument("-T", "--tags", action="store_true", help="Print tags")
    parser.add_argument(
        "-N",
        "--unwatched-first",
        action="store_true",
        help="Prioritize unwatched entries over new ones already watched",
    )
    parser.add_argument(
        "-w",
        "--watched",
        metavar="ID",
        help="Mark as watched (Accepts entry/channel id or keyword 'all')",
    )

    return parser


def print_error(message: str):
    print(f"\000message\037{message}\n \n")


def main():
    global print_error

    args = parse_args()
    config = Config(config_file=args.config)

    rc = RofiConfig()
    rc.load(args.rofi_config)
    rc.update(vars(args))

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

    printer = RofiPrinter(feeder=feeder, rofi_config=rc)
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
    try:
        main()
    except Exception as e:
        print_error(f"ERR: {e!s}")
        sys.exit(1)
