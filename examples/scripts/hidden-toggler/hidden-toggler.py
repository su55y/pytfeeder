#!/usr/bin/env -S python -u

import subprocess as sp
import sys

from pytfeeder import Config, defaults

DEFAULT_CONFIG_PATH = defaults.default_config_path()
SAVE_KB = "ctrl-s"


def run():
    config = Config(DEFAULT_CONFIG_PATH)
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
    try:
        res = run()
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        print(e)
        return 1
    else:
        return res


if __name__ == "__main__":
    sys.exit(main())
