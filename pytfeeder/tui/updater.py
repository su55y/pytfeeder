import datetime as dt
from typing import Optional

from pytfeeder.feeder import Feeder


class Updater:
    def __init__(self, feeder: Feeder) -> None:
        self.feeder = feeder
        self._status_msg = ""
        if self.feeder.config.tui.always_update or self.is_update_interval_expired():
            print("Updating...")
            if err := self.update():
                print("Update failed: %s" % err)
                exit(1)

    @property
    def status_msg(self) -> str:
        msg = ""
        if self._status_msg:
            msg = self._status_msg
            self._status_msg = ""
        return msg

    def update_lock_file(self) -> None:
        self.feeder.config.lock_file.write_text(dt.datetime.now().strftime("%s"))

    def is_update_interval_expired(self) -> bool:
        if not self.feeder.config.lock_file.exists():
            return True

        last_update = dt.datetime.fromtimestamp(
            float(self.feeder.config.lock_file.read_text())
        )
        if last_update < (
            dt.datetime.now()
            - dt.timedelta(minutes=self.feeder.config.tui.update_interval)
        ):
            self.update_lock_file()
            return True

        return False

    def update(self) -> Optional[Exception]:
        import asyncio

        before = self.feeder.unviewed_count()
        try:
            asyncio.run(self.feeder.sync_entries())
        except Exception as e:
            self._status_msg = "Update failed: %s" % e
        else:
            self.update_lock_file()
            after = self.feeder.unviewed_count()
            if before < after:
                self.feeder.update_channels()
                self._status_msg = f"{after - before} new entries"
