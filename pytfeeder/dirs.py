from functools import cache
from pathlib import Path
from os import getenv


@cache
def default_config_path() -> Path:
    if xdg_config_home := getenv("XDG_CONFIG_HOME"):
        config_home = Path(xdg_config_home)
    else:
        config_home = Path.joinpath(Path.home(), ".config")
    return Path.joinpath(config_home, __package__, "config.yaml")


@cache
def default_cachedir_path() -> Path:
    if xdg_cache_home := getenv("XDG_CACHE_HOME"):
        cache_home = Path(xdg_cache_home)
    else:
        cache_home = Path.joinpath(Path.home(), ".cache")
    return Path.joinpath(cache_home, __package__)


@cache
def default_logfile_path() -> Path:
    return default_cachedir_path().joinpath("%s.log" % __package__)


@cache
def default_storage_path() -> Path:
    return default_cachedir_path().joinpath("%s.db" % __package__)
