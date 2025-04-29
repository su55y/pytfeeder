from pathlib import Path
import tempfile
import unittest

from pytfeeder.config import Config, STORAGE_FILENAME
from pytfeeder.defaults import default_data_path


class TestDataDir(unittest.TestCase):
    def test_storage_path(self):
        self.assertEqual(
            Config(channels=list()).storage_path,
            default_data_path() / STORAGE_FILENAME,
        )
        self.assertEqual(
            Config(channels=list(), data_dir=Path("test")).storage_path,
            Path("test") / STORAGE_FILENAME,
        )
        self.assertEqual(
            Config(channels=list(), storage_path=Path("test")).storage_path,
            Path("test"),
        )

    def test_storage_path_with_config(self):
        tmp_config = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            prefix="pytfeeder_test_config",
            delete_on_close=False,
        )
        tmp_dir_path = Path(tmp_config.name).parent
        tmp_config.write(f"data_dir: {tmp_dir_path}")
        tmp_config.close()

        self.assertEqual(
            Config(channels=list(), config_file=Path(tmp_config.name)).storage_path,
            tmp_dir_path / STORAGE_FILENAME,
        )
        self.assertEqual(
            Config(
                channels=list(),
                config_file=Path(tmp_config.name),
                storage_path=Path("test"),
            ).storage_path,
            Path("test"),
        )
