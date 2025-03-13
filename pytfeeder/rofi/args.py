import argparse

from pytfeeder.defaults import default_config_path
from . import consts


def parse_args(args=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-A",
        "--alphabetic-sort",
        action="store_true",
        help="Sort channels in alphabetic order, instead of order by config",
    )
    parser.add_argument(
        "-c",
        "--config-file",
        metavar="PATH",
        default=default_config_path(),
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
        "-N",
        "--unwatched-first",
        action="store_true",
        help="Prioritize unwatched entries over new ones already watched",
    )
    parser.add_argument(
        "--separator",
        default="\n",
        metavar="STR",
        help="Line separator (default: %(default)r)",
    )
    parser.add_argument(
        "-s",
        "--sync",
        action="store_true",
        help="Updates all feeds and prints new entries count",
    )
    parser.add_argument(
        "-v",
        "--viewed",
        metavar="ID",
        help="Mark as viewed (Accepts entry/channel id or keyword 'all')",
    )

    return parser.parse_args(args=args)
