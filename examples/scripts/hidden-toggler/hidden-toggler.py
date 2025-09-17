#!/usr/bin/env -S python -u

import argparse
from pathlib import Path
import subprocess as sp
import sys

from pytfeeder import Config, defaults

DEFAULT_CONFIG_PATH = defaults.default_config_path()
SAVE_KB = "ctrl-s"


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


def run(channels_filepath: Path | None = None):
    config = Config(DEFAULT_CONFIG_PATH, channels_filepath=channels_filepath)
    if len(config.all_channels) == 0:
        print(f"No channels configured in {config.channels_filepath}")
        sys.exit(0)
    icons = ["󰄱", "\033[1;32m󰱒"]
    index = 0

    while True:
        all_channels_str = "\n".join(
            f"{i} {icons[c.hidden]} {c.title}\033[0m"
            for i, c in enumerate(config.all_channels)
        )
        if index > 0:
            opts = f"--sync --bind='ctrl-space:accept,start:{'+'.join('down' for _ in range(index))}'"
        else:
            opts = "--bind='ctrl-space:accept'"

        res = sp.run(
            f"fzf --ansi --preview='' --with-nth=2.. --accept-nth=1\
                --header '{SAVE_KB}: Save changes' --layout=reverse\
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
