import argparse
import asyncio
import logging
from pathlib import Path

from pytfeeder.config import Config
from pytfeeder.defaults import default_config_path
from pytfeeder.feeder import Feeder
from pytfeeder.rofi import RofiPrinter
from pytfeeder.storage import Storage
from pytfeeder.consts import (
    DEFAULT_ENTRY_FMT,
    DEFAULT_CHANNEL_FMT,
    DEFAULT_DATETIME_FMT,
)
from pytfeeder.utils import fetch_channel_info


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(epilog="last modification: 12.12.2024")
    parser.add_argument("-a", "--add-channel", metavar="URL", help="Add channel by url")
    parser.add_argument(
        "-c",
        "--config-file",
        default=default_config_path(),
        metavar="PATH",
        help="Location of config file (default: %(default)s)",
    )
    parser.add_argument(
        "--clean-cache",
        action="store_true",
        help="Deletes inactive channels and watched entries (with -F/--force deletes all entries)",
    )
    parser.add_argument(
        "-F", "--force", action="store_true", help="Force remove all entries"
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
        "-S", "--storage-stats", action="store_true", help="Prints storage stats"
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

    rofi_args = parser.add_argument_group("rofi mode options")
    rofi_args.add_argument(
        "--active-offset",
        type=int,
        default=1,
        metavar="INT",
        help="Index offset to mark entries as active",
    )
    rofi_args.add_argument(
        "-i",
        "--channel-id",
        metavar="ID",
        help="Prints channel feed by given channel_id",
    )
    rofi_args.add_argument(
        "--channels-fmt",
        type=lambda s: eval("'%s'" % s),
        metavar="STR",
        help=f"Channels print format (default: {DEFAULT_CHANNEL_FMT!r})",
    )
    rofi_args.add_argument(
        "--datetime-fmt",
        metavar="STR",
        help=f"Datetime key format (default: {DEFAULT_DATETIME_FMT.replace('%', '%%')!r})",
    )
    rofi_args.add_argument(
        "--entries-fmt",
        type=lambda s: eval("'%s'" % s),
        metavar="STR",
        help=f"Entries print format (default: {DEFAULT_ENTRY_FMT!r}",
    )
    rofi_args.add_argument("-f", "--feed", action="store_true", help="Prints feed")
    rofi_args.add_argument(
        "-l", "--limit", type=int, metavar="INT", help="Use custom lines limit"
    )
    rofi_args.add_argument(
        "--separator",
        default="\n",
        metavar="STR",
        help="Line separator (default: %(default)r)",
    )

    return parser.parse_args()


def init_logger(config: Config):
    logger = logging.getLogger()
    logger.setLevel(config.log_level)
    handler = logging.FileHandler(config.log_file)
    handler.setFormatter(logging.Formatter(config.log_fmt))
    logger.addHandler(handler)


def entries_stats(feeder: Feeder) -> str:
    stats = "entries count: %d (%d new)\n" % (
        feeder.stor.select_entries_count(),
        feeder.unviewed_count(),
    )
    max_title_len = max(len(c.title) for c in feeder.config.channels)
    entries_stats_dict = {
        c.title: (
            feeder.stor.select_entries_count(c.channel_id),
            feeder.unviewed_count(c.channel_id),
        )
        for c in feeder.config.channels
    }
    max_num_len = max(len(str(c)) for c, _ in entries_stats_dict.values())
    entries_stats_lines = []
    for title, (count, new) in entries_stats_dict.items():
        entries_stats_lines.append(
            f"  - {title + ':': <{max_title_len + 3}}{count:{max_num_len}d} ({new})"
        )

    stats += "\n".join(entries_stats_lines)
    return stats


def storage_file_stats(storage_path: Path) -> str:
    from datetime import datetime
    import math
    import pwd

    stat = storage_path.stat()
    user = pwd.getpwuid(stat.st_uid)[0]

    st_atime = datetime.fromtimestamp(stat.st_atime)
    st_mtime = datetime.fromtimestamp(stat.st_mtime)
    st_ctime = datetime.fromtimestamp(stat.st_ctime)

    size = ""
    if stat.st_size == 0:
        size = "0B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(stat.st_size, 1024)))
    p = math.pow(1024, i)
    s = round(stat.st_size / p, 2)
    size = "%s %s" % (s, size_name[i])

    return "{tab}owner: {user}\n{tab}size: {size}\n{tab}ctime: {ctime}\n{tab}mtime: {mtime}\n{tab}atime: {atime}".format(
        tab="  - ",
        user=user,
        size=size,
        ctime=st_ctime,
        mtime=st_mtime,
        atime=st_atime,
    )


def run():
    args = parse_args()

    config_args = {"config_file": args.config_file}
    if args.rofi:
        config_args["datetime_fmt"] = args.datetime_fmt
        config_args["entries_fmt"] = args.entries_fmt
        config_args["channels_fmt"] = args.channels_fmt

    config = Config(**config_args)
    if not config:
        exit(1)

    if args.print_config:
        print(config)
        exit(0)

    if not config.cache_dir.exists():
        config.cache_dir.mkdir(parents=True)

    if config.log_level > 0:
        init_logger(config)

    if args.add_channel:
        new_channel = fetch_channel_info(args.add_channel)
        if not new_channel:
            exit(1)
        config.channels.append(new_channel)
        config.dump(args.config_file)
        print(f"{new_channel.title!r} just added")
        exit(0)

    feeder = Feeder(config, Storage(config.storage_path))

    if args.storage_stats:
        print("storage stats:\n")
        print(entries_stats(feeder))
        print("\nfile stats:\n" + storage_file_stats(config.storage_path))
        exit(0)

    if args.clean_cache:
        feeder.clean_cache(args.force)

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
