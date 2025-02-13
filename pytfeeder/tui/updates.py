import datetime as dt
from pathlib import Path
from typing import Optional

from pytfeeder.feeder import Feeder


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


def update(feeder: Feeder) -> Optional[str]:
    import asyncio

    update_status_msg = None
    before = feeder.unviewed_count()
    try:
        asyncio.run(feeder.sync_entries())
    except Exception as e:
        update_status_msg = "Update failed: %s" % e
        print(update_status_msg)
    else:
        update_lock_file(feeder.config.update_lock_file)
        after = feeder.unviewed_count()
        if before < after:
            feeder.update_channels()
            update_status_msg = f"{after - before} new entries"

    return update_status_msg
