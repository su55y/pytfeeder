import argparse
from typing import List

from pytfeeder.defaults import default_config_path
from . import consts


def format_keybindings() -> List[str]:
    max_keys_w = max(len(keys) for keys, _ in consts.HELP_KEYBINDINGS)
    tab = " " * 4
    return [
        f"{tab}{keys:<{max_keys_w}}{tab}{desc}"
        for keys, desc in consts.HELP_KEYBINDINGS
    ]


def parse_args() -> argparse.Namespace:
    def format_epilog() -> str:
        keybinds_str = "\n".join(format_keybindings())
        return f"{consts.OPTIONS_DESCRIPTION}\n\nkeybindings:\n{keybinds_str}\n"

    parser = argparse.ArgumentParser(
        epilog=format_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-A",
        "--alphabetic-sort",
        action="store_true",
        help="Sort channels in alphabetic order, instead of order by config",
    )
    parser.add_argument(
        "--channels-fmt",
        metavar="STR",
        help=f"Channels format (default: {consts.DEFAULT_CHANNELS_FMT!r})",
    )
    parser.add_argument(
        "-c",
        "--config",
        metavar="PATH",
        default=default_config_path(),
        help="Config path (default: %(default)s)",
    )
    parser.add_argument(
        "--datetime-fmt",
        metavar="STR",
        help=f"Datetime format for `{{published}}` format key (default: {consts.DEFAULT_DATETIME_FMT.replace('%', '%%')!r})",
    )
    parser.add_argument(
        "--download-output",
        metavar="STR",
        help=f"Download output template (yt-dlp's `-o` option) (default: {consts.DEFAULT_DOWNLOAD_OUTPUT.replace('%', '%%')!r})",
    )
    parser.add_argument(
        "--feed-entries-fmt",
        metavar="STR",
        help=f"Feed entries format (default: {consts.DEFAULT_FEED_ENTRIES_FMT!r})",
    )
    parser.add_argument(
        "--entries-fmt",
        metavar="STR",
        help=f"Entries format (default: {consts.DEFAULT_ENTRIES_FMT!r})",
    )
    parser.add_argument(
        "--hide-feed", action="store_true", help="Hide 'Feed' in channels list"
    )
    parser.add_argument(
        "--hide-statusbar", action="store_true", help="Turn off statusbar visability"
    )
    parser.add_argument(
        "-l",
        "--limit",
        default=0,
        type=int,
        metavar="INT",
        help="Channels feed limit. Overrides config value (default: None)",
    )
    parser.add_argument(
        "-L",
        "--feed-limit",
        default=0,
        type=int,
        metavar="INT",
        help="Feed limit. Overrides config value (default: None)",
    )
    parser.add_argument(
        "--last-update-fmt",
        help=f"{{last_update}} status key datetime format (default: {consts.DEFAULT_LAST_UPDATE_FMT.replace('%', '%%')!r})",
    )
    parser.add_argument(
        "--macro1",
        metavar="STR",
        help="F1 macro",
    )
    parser.add_argument(
        "--macro2",
        metavar="STR",
        help="F2 macro",
    )
    parser.add_argument(
        "--macro3",
        metavar="STR",
        help="F4 macro",
    )
    parser.add_argument(
        "--macro4",
        metavar="STR",
        help="F4 macro",
    )
    parser.add_argument(
        "--new-mark",
        default=consts.DEFAULT_NEW_MARK,
        metavar="STR",
        help="New mark format (default: %(default)r)",
    )
    parser.add_argument(
        "-n",
        "--no-update",
        action="store_true",
        help="Never update on startup",
    )
    parser.add_argument(
        "-N",
        "--unwatched-first",
        action="store_true",
        help="Prioritize unwatched entries over new ones already watched",
    )
    parser.add_argument(
        "--status-fmt",
        metavar="STR",
        help=f"Status bar format (default: {consts.DEFAULT_STATUS_FMT!r})",
    )
    parser.add_argument(
        "-u",
        "--update-interval",
        metavar="INT",
        type=int,
        help=f"Update interval in minutes (default: {consts.DEFAULT_UPDATE_INTERVAL_MINS})",
    )
    parser.add_argument(
        "-U", "--always-update", action="store_true", help="Update all feeds on startup"
    )
    return parser.parse_args()
