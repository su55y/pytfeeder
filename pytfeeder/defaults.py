from pathlib import Path
from os import getenv
from tempfile import gettempdir


def default_config_path() -> Path:
    if xdg_config_home := getenv("XDG_CONFIG_HOME"):
        config_home = Path(xdg_config_home)
    else:
        config_home = Path.home().joinpath(".config")
    return config_home.joinpath("pytfeeder", "config.yaml")


def default_channels_filepath() -> Path:
    if xdg_config_home := getenv("XDG_CONFIG_HOME"):
        config_home = Path(xdg_config_home)
    else:
        config_home = Path.home().joinpath(".config")
    return config_home.joinpath("pytfeeder", "channels.yaml")


def default_data_path() -> Path:
    if xdg_data_home := getenv("XDG_DATA_HOME"):
        data_home = Path(xdg_data_home)
    else:
        data_home = Path.home().joinpath(".local", "share")
    return data_home.joinpath("pytfeeder")


def default_lockfile_path() -> Path:
    return Path(gettempdir()) / "pytfeeder_update.lock"
