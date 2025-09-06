import datetime as dt
from pathlib import Path
import tempfile
import unittest
import os

from pytfeeder import Config, Storage, Feeder
from pytfeeder.entry_points.run_pytfeeder import stats_fmt_str


class TestStatsFmt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sf, sf_name = tempfile.mkstemp(prefix="test_storage", suffix=".db")
        os.close(sf)
        cls.storage_path = Path(sf_name)

        cls.last_update = dt.datetime.now()

        lf, lf_name = tempfile.mkstemp(prefix="pytfeeder_update", suffix=".lock")
        os.write(lf, f"0:{cls.last_update.strftime('%s')}".encode())
        os.close(lf)
        cls.lock_file = Path(lf_name)

    @classmethod
    def tearDownClass(cls):
        cls.storage_path.unlink(missing_ok=True)
        cls.lock_file.unlink(missing_ok=True)

    def test_stats_fmt(self):
        f = Feeder(Config(lock_file=self.lock_file), Storage(self.storage_path))
        for inp, exp in [
            ("{last_update}", self.last_update.strftime("%D %T")),
            ("{last_update#%T}", self.last_update.strftime("%T")),
            (
                "{total:2d}--{last_update#%b%b}",
                " 0--" + self.last_update.strftime("%b%b"),
            ),
        ]:
            self.assertEqual(stats_fmt_str(f, inp), exp)

        with self.assertRaises(KeyError):
            stats_fmt_str(f, "{last_update#}")
