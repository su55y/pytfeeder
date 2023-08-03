from functools import cache
from pathlib import Path
from os import getenv


@cache
def default_config_path() -> Path:
    if xdg_config_home := getenv("XDG_CONFIG_HOME"):
        config_home = Path(xdg_config_home)
    else:
        config_home = Path.home().joinpath(".config")
    return config_home.joinpath("pytfeeder/config.yaml")


@cache
def default_cachedir_path() -> Path:
    if xdg_cache_home := getenv("XDG_CACHE_HOME"):
        cache_home = Path(xdg_cache_home)
    else:
        cache_home = Path.home().joinpath(".cache")
    return cache_home.joinpath("pytfeeder")
