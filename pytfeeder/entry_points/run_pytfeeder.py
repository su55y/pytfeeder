import argparse
import asyncio
from pathlib import Path
import sys

from pytfeeder import Config, Feeder, Storage, utils, defaults, __version__
from pytfeeder.logger import LogLevel, init_logger

STATS_FMT_KEYS = """
stats-fmt keys:
    {total}                 - total entries count (excluding deleted)
    {unwatched}             - new entries count
    {deleted}               - marked as deleted entries count
    {last_update}           - last update datetime, can be used with fmt like `{last_update#%%D %%T}`
    {channels_with_updates} - channels with new entries
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        epilog=STATS_FMT_KEYS, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "-a", "--add", metavar="URL", help="Add channel to channels config by url"
    )
    parser.add_argument(
        "-c",
        "--config",
        default=defaults.default_config_path(),
        metavar="PATH",
        type=Path,
        help="Location of config file (default: %(default)s)",
    )
    parser.add_argument(
        "--clean-cache",
        action="store_true",
        help="Remove old entries from database that was marked as deleted and execute VACUUM",
    )
    parser.add_argument(
        "--delete-inactive",
        action="store_true",
        help="Remove entries with channel_id that unknown to channels.yaml and execute VACUUM",
    )
    parser.add_argument(
        "-H",
        "--ignore-hidden",
        action="store_true",
        help="Excludes updates count of hidden channels on `--sync`",
    )
    parser.add_argument(
        "-p",
        "--dump-config",
        action="store_true",
        help="Dump the current config in yaml format",
    )
    parser.add_argument(
        "-f", "--stats-fmt", metavar="STR", help="Print formatted stats"
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
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Verbosity level: -v: prints progress on sync, -vv prints debug log to stdout",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser.parse_args()


def storage_stats(feeder: Feeder) -> str:
    max_title_len = max(len(c.title) for c in feeder.config.channels)
    max_title_len = max(max_title_len, 24)
    channels_map = {c.channel_id: c.title for c in feeder.config.all_channels}
    stats = feeder.stor.select_stats()

    total_total = feeder.stor.select_entries_count()
    total_count = feeder.total_entries_count()
    total_deleted = feeder.deleted_count()
    total_new = feeder.unwatched_count()

    c1, c2, c3, c4 = (
        max(len(str(total_count)), len('count')),
        max(len(str(total_new)), len('new')),
        max(len(str(total_deleted)), len('del')),
        max(len(str(total_total)), len('total')),
    )
    stats_line_width = max_title_len + c1 + c2 + c3 + c4 + 4

    total_nums = f"{total_count:{c1}d}|{total_new:{c2}d}|{total_deleted:{c3}d}|{total_total:{c4}d}"
    total_stats_footer = (
        f"{'='*stats_line_width}\n{'TOTAL':<{max_title_len+1}}|{total_nums}"
    )

    header = f"{'title':^{max_title_len+1}}|{'count':^{c1}}|{'new':^{c2}}|{'del':^{c3}}|{'total':^{c4}}"
    header += f"\n{'-'*len(header)}"

    entries_stats_str = ""
    deleted_stats_str = ""
    for channel_id, total, count, new, deleted in stats:
        nums = f"{count:{c1}d}|{new:{c2}d}|{deleted:{c3}d}|{total:{c4}d}"
        title = channels_map.get(channel_id)
        if title is None:
            deleted_stats_str += f"{channel_id:<{max_title_len+1}}|{nums}\n"
        else:
            entries_stats_str += f"{title:<{max_title_len+1}}|{nums}\n"

    unknown_section = ""
    if deleted_stats_str:
        unknown_section = (
            f"{' UNKNOWN CHANNELS ':-^{stats_line_width}}\n{deleted_stats_str}"
        )

    return f"{header}\n{entries_stats_str}{unknown_section}{total_stats_footer}\n"


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


def stats_fmt_str(feeder: Feeder, fmt: str) -> str:
    count = total = unwatched = deleted = 0
    last_update = ""
    channels_with_updates = ""

    if "{count" in fmt:
        count = feeder.total_entries_count()
    if "{total" in fmt:
        total = feeder.stor.select_entries_count()
    if "{unwatched" in fmt:
        unwatched = feeder.unwatched_count()
    if "{deleted" in fmt:
        deleted = feeder.deleted_count()
    if "{last_update" in fmt:
        import re

        fmts = ["%D %T"]

        def replacer_(match: re.Match[str]) -> str:
            (f_,) = match.groups()
            if f_:
                fmts.append(f_[1:])
            return "{last_update}"

        fmt = re.sub(r"\{last_update(#[^}]+)?\}", replacer_, fmt)

        lu = feeder.updater.last_update
        last_update = lu.strftime(fmts.pop()) if lu else "Unknown"
    if "{channels_with_updates" in fmt:
        channels_with_updates = "\n".join(
            c.title for c in feeder.channels if c.have_updates
        )

    return fmt.format(
        count=count,
        total=total,
        unwatched=unwatched,
        deleted=deleted,
        last_update=last_update,
        channels_with_updates=channels_with_updates,
    )


def main():
    args = parse_args()
    config = Config(config_file=args.config)

    if args.dump_config:
        print(config.dump(), end="")
        sys.exit(0)

    if not config.data_dir.exists():
        config.data_dir.mkdir(parents=True)

    if args.verbose > 1:
        config.logger.file = None
        config.logger.stream = True
        config.logger.level = LogLevel.DEBUG
    init_logger(config.logger)

    if args.add:
        channel_url = args.add
        if not config.channels_filepath.exists():
            answ = input(
                f"Channels file {config.channels_filepath} not exists,\ncreate it?: "
            )
            if not answ.lower().startswith("y"):
                sys.exit(0)
            config.channels_filepath.touch(0o644, exist_ok=False)

        try:
            new_channel = utils.fetch_channel_info(channel_url)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

        if channel := {c.channel_id: c for c in config.all_channels}.get(
            new_channel.channel_id
        ):
            print(
                f"Channel {channel.title!r} ({channel.channel_id = }) already exists in {config.channels_filepath!s}"
            )
            sys.exit(1)
        config.all_channels.append(new_channel)
        config.dump_channels()
        print(f"{new_channel.title!r} just added")
        sys.exit(0)

    feeder = Feeder(config, Storage(config.storage_path))

    if args.storage_stats:
        print(storage_stats(feeder))
        print("File stats:\n" + storage_file_stats(config.storage_path))
        sys.exit(0)

    if args.stats_fmt:
        print(stats_fmt_str(feeder, args.stats_fmt))
        sys.exit(0)

    if args.clean_cache:
        count = feeder.clean_cache()
        print(f"{count} entries were deleted")
        sys.exit(0)
    elif args.delete_inactive:
        count = feeder.delete_inactive()
        print(f"{count} entries were deleted")
        sys.exit(0)

    if args.sync:
        (new, err) = asyncio.run(
            feeder.sync_entries(
                verbose=args.verbose > 0,
                report_hidden=not args.ignore_hidden,
            )
        )
        if err:
            print(f"Error: {err}")
        else:
            print(new)

    elif args.unwatched:
        print(feeder.unwatched_count())


if __name__ == "__main__":
    main()
