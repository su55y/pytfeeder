import argparse
from pathlib import Path

from pytfeeder.config import DEFAULT_UPDATE_INTERVAL_MINS
from pytfeeder.defaults import default_config_path, default_channels_filepath
from . import consts


def format_keybindings(macros: dict[str, str] = {}) -> list[str]:
    max_keys_w = max(len(keys) for keys in consts.HELP_KEYBINDINGS)
    tab = " " * 4
    if len(macros):
        del consts.HELP_KEYBINDINGS["F1-F4"]
        for key in macros:
            if macros[key]:
                consts.HELP_KEYBINDINGS[key] = macros[key]
    return [
        f"{tab}{keys:<{max_keys_w}}{tab}{desc}"
        for keys, desc in consts.HELP_KEYBINDINGS.items()
    ]


def parse_args() -> argparse.Namespace:
    return create_parser().parse_args()


def create_parser() -> argparse.ArgumentParser:
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
        type=Path,
        help="Config path (default: %(default)s)",
    )
    parser.add_argument(
        "-C",
        "--channels-file",
        metavar="PATH",
        type=Path,
        help=f"Channels path (default: {default_channels_filepath()})",
    )
    parser.add_argument(
        "-D",
        "--debug",
        action="store_true",
        help="Print debug log to stdout",
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
        "--channel-feed-limit",
        type=int,
        metavar="INT",
        help="Channels feed limit (default: None)",
    )
    parser.add_argument(
        "-L",
        "--feed-limit",
        type=int,
        metavar="INT",
        help="Feed limit (default: None)",
    )
    parser.add_argument(
        "--last-update-fmt",
        help=f"{{last_update}} status key datetime format (default: {consts.DEFAULT_LAST_UPDATE_FMT.replace('%', '%%')!r})",
    )
    parser.add_argument(
        "--macro1",
        metavar="CMD",
        help="F1 macro",
    )
    parser.add_argument(
        "--macro2",
        metavar="CMD",
        help="F2 macro",
    )
    parser.add_argument(
        "--macro3",
        metavar="CMD",
        help="F3 macro",
    )
    parser.add_argument(
        "--macro4",
        metavar="CMD",
        help="F4 macro",
    )
    parser.add_argument(
        "--new-mark",
        metavar="STR",
        help=f"New mark string (default: {consts.DEFAULT_NEW_MARK!r})",
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
        help="Prioritize unwatched entries over watched",
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
        help=f"Update interval in minutes (default: {DEFAULT_UPDATE_INTERVAL_MINS})",
    )
    parser.add_argument(
        "-U", "--always-update", action="store_true", help="Update all feeds on startup"
    )
    return parser
