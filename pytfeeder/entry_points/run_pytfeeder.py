import argparse
import asyncio
from pathlib import Path
import sys

from pytfeeder import Config, Feeder, Storage, utils, defaults, __version__
from pytfeeder.logger import init_logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--add-channel", metavar="URL", help="Add channel by url")
    parser.add_argument(
        "-c",
        "--config-file",
        default=defaults.default_config_path(),
        metavar="PATH",
        type=Path,
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
        "-u", "--unwatched", action="store_true", help="Prints unwatched entries count"
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser.parse_args()


def entries_stats(feeder: Feeder) -> str:
    max_title_len = max(len(c.title) for c in feeder.config.channels)
    channels_map = {c.channel_id: c.title for c in feeder.config.channels}
    stats = feeder.stor.select_stats()
    c1, c2, c3 = 1, 1, 1
    deleted_channels = {}
    for cid, c, n, d in stats:
        c1 = max(len(str(c)), c1)
        c2 = max(len(str(n)), c2)
        c3 = max(len(str(d)), c3)
        if cid not in channels_map:
            deleted_channels[cid] = (c, n, d)

    entries_stats_str = ""
    deleted_stats_str = ""
    for channel_id, count, new, deleted in stats:
        nums = f"{count:{c1}d} | {new:{c2}d} | {deleted:{c3}d}"
        title = channels_map.get(channel_id)
        if title is None:
            deleted_stats_str += f"{channel_id:<24} | {nums}\n"
        else:
            entries_stats_str += f"{title:<{max_title_len}} | {nums}\n"
    header = (
        f"{'TITLE':^{max_title_len}} |{'TOT':^{c1+2}}|{'NEW':^{c2+2}}|{'DEL':^{c3+2}}"
    )
    header += f"\n{'-'*len(header)}"
    return f"\n{header}\n{entries_stats_str}\nDeleted channels:\n{deleted_stats_str}"


def storage_file_stats(storage_path: Path) -> str:
    from datetime import datetime
    import pwd

    stat = storage_path.stat()
    return "{tab}Path:   {path}\n{tab}Uid:    {user}\n{tab}Size:   {size}\n{tab}Change: {ctime}\n{tab}Modify: {mtime}\n{tab}Access: {atime}".format(
        tab="  - ",
        path=storage_path,
        user="%s/%s" % (stat.st_uid, pwd.getpwuid(stat.st_uid)[0]),
        size=utils.human_readable_size(stat.st_size),
        ctime=datetime.fromtimestamp(stat.st_atime),
        mtime=datetime.fromtimestamp(stat.st_mtime),
        atime=datetime.fromtimestamp(stat.st_ctime),
    )


def run():
    args = parse_args()
    config = Config(config_file=args.config_file)

    if args.print_config:
        print(config)
        sys.exit(0)

    if not config.data_dir.exists():
        config.data_dir.mkdir(parents=True)

    init_logger(config.logger)

    if args.add_channel:
        try:
            new_channel = utils.fetch_channel_info(args.add_channel)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

        if channel := {c.channel_id: c for c in config.channels}.get(
            new_channel.channel_id
        ):
            print(
                f"Channel {channel.title!r} ({channel.channel_id = }) already exists in {config.channels_filepath!s}"
            )
            sys.exit(1)
        config.channels.append(new_channel)
        config.dump_channels()
        print(f"{new_channel.title!r} just added")
        sys.exit(0)

    feeder = Feeder(config, Storage(config.storage_path))

    if args.storage_stats:
        total = feeder.total_entries_count(exclude_deleted=False)
        deleted = total - feeder.total_entries_count(exclude_deleted=True)
        print(
            " Total entries count: {total} (new: {new}, deleted: {deleted})\n".format(
                total=total,
                new=feeder.unwatched_count(),
                deleted=deleted,
            ),
            end="",
        )
        print(entries_stats(feeder))
        print(" File stats:\n" + storage_file_stats(config.storage_path))
        sys.exit(0)

    if args.clean_cache:
        feeder.clean_cache(args.force)

    if args.sync:
        (new, err) = asyncio.run(feeder.sync_entries())
        if err:
            print(f"Error: {err}")
        else:
            print(new)

    elif args.unwatched:
        print(feeder.unwatched_count())
