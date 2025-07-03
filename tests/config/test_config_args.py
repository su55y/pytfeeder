from pathlib import Path
import tempfile
import unittest

from pytfeeder.config import Config

from .config_mocks import raw_channels_yaml_mock, channels_mock


class TestConfigArgs(unittest.TestCase):
    def setUp(self):
        self.channels = channels_mock.copy()

    def test_pass_channels(self):
        c = Config(channels=self.channels)
        self.assertEqual(c.all_channels, channels_mock)

    def test_pass_channels_and_channels_filepath(self):
        c = Config(
            channels=self.channels,
            channels_filepath=Path(),
        )
        self.assertEqual(c.all_channels, channels_mock)

    def test_pass_channels_filepath(self):
        channels_tmp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            prefix="pytfeeder_test_channels",
            delete_on_close=False,
        )
        channels_tmp_file.write(raw_channels_yaml_mock)
        channels_tmp_file.close()

        c = Config(channels_filepath=Path(channels_tmp_file.name))
        self.assertEqual(c.all_channels, channels_mock)

    def test_pass_config_file(self):
        channels_tmp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            prefix="pytfeeder_test_channels",
            delete_on_close=False,
        )
        channels_tmp_file.write(raw_channels_yaml_mock)
        channels_tmp_file.close()

        tmp_config = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            prefix="pytfeeder_test_config",
            delete_on_close=False,
        )
        tmp_config.write(f"channels_filepath: {channels_tmp_file.name}")
        tmp_config.close()

        c = Config(config_file=Path(tmp_config.name))
        self.assertEqual(c.all_channels, channels_mock)
