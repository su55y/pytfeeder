import datetime as dt
from pathlib import Path


def update_lock_file(file: Path) -> None:
    file.write_text(dt.datetime.now().strftime("%s"))


def is_update_interval_expired(file: Path, mins: int) -> bool:
    if not file.exists():
        return True

    last_update = dt.datetime.fromtimestamp(float(file.read_text()))
    if last_update < (dt.datetime.now() - dt.timedelta(minutes=mins)):
        update_lock_file(file)
        return True

    return False
