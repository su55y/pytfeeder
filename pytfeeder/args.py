import argparse
from functools import cache
from pathlib import Path
from os import getenv

from pytfeeder import __name__ as PACKAGENAME


@cache
def default_cache_path() -> Path:
    if xdg_cache_home := getenv("XDG_CACHE_HOME"):
        cache_home = Path(xdg_cache_home)
    else:
        cache_home = Path.joinpath(Path.home(), ".cache")
    return Path.joinpath(cache_home, PACKAGENAME)


def default_config_path(config_name="config.yaml") -> Path:
    if xdg_config_home := getenv("XDG_CONFIG_HOME"):
        config_home = Path(xdg_config_home)
    else:
        config_home = Path.joinpath(Path.home(), ".config")
    return Path.joinpath(config_home, PACKAGENAME, config_name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config-file",
        default=default_config_path(),
        help="Location of config file (default: %(default)s)",
    )
    parser.add_argument(
        "-d",
        "--cache-dir",
        default=default_cache_path(),
        help="Location of cache directory (default: %(default)s)",
    )
    parser.add_argument(
        "-l",
        "--log-file",
        default=default_cache_path().joinpath("%s.log" % PACKAGENAME),
        help="Location of log file (default: %(default)s)",
    )
    parser.add_argument("-i", "--channel-id", help="print channel feed")
    parser.add_argument("-s", "--sync", action="store_true", help="just update feeds")
    parser.add_argument("-f", "--feed", action="store_true", help="common feed")

    return parser.parse_args()
