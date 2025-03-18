import argparse
import asyncio
import logging
from pathlib import Path

from pytfeeder.config import Config
from pytfeeder.defaults import default_config_path
from pytfeeder.feeder import Feeder
from pytfeeder.storage import Storage
from pytfeeder.utils import fetch_channel_info, human_readable_size
from pytfeeder import __version__


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
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
        "-F",
        "--force",
        action="store_true",
        help="Remove all entries when used with `--clean-cache`",
    )
    parser.add_argument(
        "-p", "--print-config", action="store_true", help="Prints config"
    )
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
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser.parse_args()


def init_logger(config: Config):
    logger = logging.getLogger()
    logger.setLevel(config.log_level)
    handler = logging.FileHandler(config.log_file)
    handler.setFormatter(logging.Formatter(config.log_fmt))
    logger.addHandler(handler)


def entries_stats(feeder: Feeder) -> str:
    max_title_len = max(len(c.title) for c in feeder.config.channels)
    channels_map = {c.channel_id: c.title for c in feeder.config.channels}
    stats = feeder.stor.select_stats()
    max_count_number_len = max(len(str(c)) for _, c, _ in stats) if len(stats) else 1
    entries_stats_str = ""
    for channel_id, count, new in stats:
        title = channels_map.get(channel_id, f"{channel_id} (DELETED)")
        entries_stats_str += f"  - {title + ':': <{max_title_len + 3}}{count:{max_count_number_len}d} ({new})\n"
    return entries_stats_str


def storage_file_stats(storage_path: Path) -> str:
    from datetime import datetime
    import pwd

    stat = storage_path.stat()
    return "{tab}Path:   {path}\n{tab}Uid:    {user}\n{tab}Size:   {size}\n{tab}Change: {ctime}\n{tab}Modify: {mtime}\n{tab}Access: {atime}".format(
        tab="  - ",
        path=storage_path,
        user="%s/%s" % (stat.st_uid, pwd.getpwuid(stat.st_uid)[0]),
        size=human_readable_size(stat.st_size),
        ctime=datetime.fromtimestamp(stat.st_atime),
        mtime=datetime.fromtimestamp(stat.st_mtime),
        atime=datetime.fromtimestamp(stat.st_ctime),
    )


def run():
    args = parse_args()
    config = Config(config_file=args.config_file)
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
        config.dump_channels()
        print(f"{new_channel.title!r} just added")
        exit(0)

    feeder = Feeder(config, Storage(config.storage_path))

    if args.storage_stats:
        print(
            " Total entries count: {total} ({new} new)\n".format(
                total=feeder.stor.select_entries_count(),
                new=feeder.unviewed_count(),
            ),
            end="",
        )
        print(entries_stats(feeder))
        print(" File stats:\n" + storage_file_stats(config.storage_path))
        exit(0)

    if args.clean_cache:
        feeder.clean_cache(args.force)

    before_update = 0
    if args.sync:
        before_update = feeder.unviewed_count()
        asyncio.run(feeder.sync_entries())
        print(feeder.unviewed_count() - before_update)
    elif args.unviewed:
        print(feeder.unviewed_count())
