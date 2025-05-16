from pathlib import Path
import tempfile
import unittest

from pytfeeder.config import Config
from pytfeeder.models import Channel

from .config_mocks import raw_channels_yaml_mock, channels_mock


class TestDumpChannels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.channels_tmp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            prefix="pytfeeder_test_channels",
            delete_on_close=False,
        )
        cls.channels_tmp_file.write(raw_channels_yaml_mock)
        cls.channels_tmp_file.close()
        cls.channels_path = Path(cls.channels_tmp_file.name)
        tmp_c = Config(channels_filepath=cls.channels_path)
        assert tmp_c.channels == channels_mock

    def test_dump_channels(self):
        new_channel = Channel(channel_id="abcdefghijklmnopqrstuvw2", title="Channel 3")
        channels = channels_mock.copy()
        channels.append(new_channel)

        old_config = Config(channels_filepath=self.channels_path)
        old_config.channels.append(new_channel)
        old_config.dump_channels()

        c = Config(channels_filepath=self.channels_path)
        self.assertEqual(c.channels, channels)

    def test_dump_channels_format(self):
        c = Config(channels_filepath=self.channels_path)
        c.channels = []
        c.dump_channels()
        with open(self.channels_path) as f:
            self.assertEqual(f.read(), "[]\n")
        self.assertEqual(Config(channels_filepath=self.channels_path).channels, [])

        c.channels = channels_mock.copy()
        c.dump_channels()
        with open(self.channels_path) as f2:
            self.assertEqual(f2.read(), raw_channels_yaml_mock)
