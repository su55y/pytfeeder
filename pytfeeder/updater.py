from pathlib import Path
import datetime as dt


class Updater:
    def __init__(self, lock_file: Path, update_interval: int) -> None:
        self.fails = 0
        self.last_update = dt.datetime.now() - dt.timedelta(minutes=update_interval + 1)
        self.lock_file = lock_file
        self.max_retries = 5
        self.update_interval = update_interval
        self._state_from_file = False

        if self.lock_file.exists():
            self._read_state()

    def _read_state(self) -> None:
        try:
            fails, lu = self.lock_file.read_text().split(":", maxsplit=1)
            self.fails = int(fails)
            self.last_update = dt.datetime.fromtimestamp(float(lu))
            self._state_from_file = True
        except Exception as e:
            raise Exception(f"Can't read update state: {e}")

    @property
    def is_update_expired(self) -> bool:
        if self.fails > 0:
            return self.fails < self.max_retries
        return self.last_update < (
            dt.datetime.now() - dt.timedelta(minutes=self.update_interval)
        )

    def update_lock_file(self, failed: bool) -> None:
        if not self._state_from_file or not failed:
            self.last_update = dt.datetime.now()
        if failed:
            self.fails += failed
        else:
            self.fails = 0
        try:
            self.lock_file.write_text(f"{self.fails}:{self.last_update.strftime('%s')}")
        except Exception as e:
            raise Exception(f"Can't update lock file: {e}")
