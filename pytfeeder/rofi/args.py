import argparse
from pathlib import Path

from pytfeeder.defaults import default_config_path
from . import consts


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
        "-l",
        "--channel-feed-limit",
        type=int,
        metavar="INT",
        help=f"Channels feed limit. Overrides config value (default: {consts.DEFAULT_CHANNEL_FEED_LIMIT})",
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
        help=f"Channels print format (default: {consts.DEFAULT_CHANNELS_FMT!r})",
    )
    parser.add_argument(
        "--datetime-fmt",
        metavar="STR",
        help=f"Datetime key format (default: {consts.DEFAULT_DATETIME_FMT.replace('%', '%%')!r})",
    )
    parser.add_argument(
        "--entries-fmt",
        type=lambda s: eval("'%s'" % s),
        metavar="STR",
        help=f"Entries print format (default: {consts.DEFAULT_ENTRIES_FMT!r}",
    )
    parser.add_argument("-f", "--feed", action="store_true", help="Prints feed")
    parser.add_argument(
        "--feed-entries-fmt",
        type=lambda s: eval("'%s'" % s),
        metavar="STR",
        help=f"Feed entries format (default: {consts.DEFAULT_ENTRIES_FMT!r})",
    )
    parser.add_argument(
        "-L",
        "--feed-limit",
        type=int,
        metavar="INT",
        help=f"Feed limit. Overrides config value (default: {consts.DEFAULT_FEED_LIMIT})",
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
