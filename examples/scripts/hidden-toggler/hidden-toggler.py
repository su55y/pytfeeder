#!/usr/bin/env -S python -u

import argparse
from pathlib import Path
import subprocess as sp
import sys

from pytfeeder import Config, defaults, Storage

DEFAULT_CONFIG_PATH = defaults.default_config_path()
SAVE_KB = "ctrl-s"
TOGGLE_KB = "ctrl-space"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-C",
        "--channels-file",
        type=Path,
        metavar="PATH",
        help=f"channels path (default: {defaults.default_channels_filepath()})",
    )
    return parser.parse_args()


def run(channels_filepath: Path | None = None) -> int:
    config = Config(DEFAULT_CONFIG_PATH, channels_filepath=channels_filepath)
    stor = Storage(db_file=config.storage_path)
    stats = stor.select_channels_stats()
    for c in config.all_channels:
        stat = stats.get(c.channel_id)
        if stat is None:
            continue
        count, unwatched = stat
        c.entries_count = count
        c.have_updates = bool(unwatched)
        c.unwatched_count = unwatched

    if len(config.all_channels) == 0:
        print(f"No channels configured in {config.channels_filepath}")
        sys.exit(0)
    icons = ["󰄱", "\033[1;32m󰱒"]
    index = 0

    config.reset_channels()
    _ = len(config.all_channels)
    while True:
        all_channels_str = "\n".join(
            f"{i} {icons[c.hidden]} {'\033[3;2m' if c.entries_count == 0 else ''}{c.title} ({c.unwatched_count}/{c.entries_count})\033[0m"
            for i, c in enumerate(config.all_channels)
        )
        if index > 0:
            opts = f"--sync --bind='{TOGGLE_KB}:accept,start:{'+'.join('down' for _ in range(index))}'"
        else:
            opts = f"--bind='{TOGGLE_KB}:accept'"

        res = sp.run(
            f"fzf --ansi --preview='' --with-nth=2.. --accept-nth=1\
                --header '{TOGGLE_KB}: Toggle hidden, {SAVE_KB}: Save changes' --layout=reverse\
                --expect='{SAVE_KB}' {opts}",
            input=all_channels_str,
            capture_output=True,
            check=False,
            shell=True,
            text=True,
        )

        if res.returncode != 0:
            return res.returncode

        if res.stdout.startswith(SAVE_KB):
            config.dump_channels()
            print(f"Changes saved to {config.channels_filepath}")
            return 0

        index = int(res.stdout)
        if index not in range(len(config.all_channels)):
            return 1
        config.all_channels[index].hidden ^= True


def main() -> int:
    args = parse_args()
    try:
        res = run(args.channels_file)
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        print(e)
        return 1
    else:
        return res


if __name__ == "__main__":
    sys.exit(main())
