import unittest
import sys

from pytfeeder import Config

DEFAULT_CONFIG_YAML_PATHS = """
channels_filepath: {XDG_CONFIG_HOME}/pytfeeder/channels.yaml
data_dir: {XDG_DATA_HOME}/pytfeeder
lock_file: /tmp/pytfeeder_update.lock
""".strip()

DEFAULT_CONFIG_YAML = r"""
logger:
  file: null
  fmt: null
  level: notset
  stream: false
rofi:
  alphabetic_sort: false
  channel_feed_limit: -1
  channels_fmt: "{title}\0info\x1F{id}"
  datetime_fmt: '%D %T'
  entries_fmt: "{title}\0info\x1F{id}\x1Fmeta\x1F{meta}"
  feed_entries_fmt: "{title}\0info\x1F{id}\x1Fmeta\x1F{meta}"
  feed_limit: -1
  separator: "\n"
  unwatched_first: false
tui:
  alphabetic_sort: false
  always_update: false
  channel_feed_limit: -1
  channels_fmt: '{index} {new_mark} {unwatched_total} {title}'
  color_accent: red
  color_black: black
  color_white: white
  datetime_fmt: '%b %d'
  download_output: ~/Videos/YouTube/%(uploader)s/%(title)s.%(ext)s
  entries_fmt: '{index} {new_mark} {published} {title}'
  feed_entries_fmt: '{index} {new_mark} {published} {channel_title} {title}'
  feed_limit: -1
  hide_feed: false
  hide_statusbar: false
  last_update_fmt: '%D %T'
  macro1: ''
  macro2: ''
  macro3: ''
  macro4: ''
  new_mark: N
  no_update: false
  status_fmt: '{msg} {index} {title} {keybinds}'
  unwatched_first: false
  update_interval: 30
""".strip()


class TestDumpConfig(unittest.TestCase):
    def test_default_config_dump(self):
        c = Config()
        dump_lines = c.dump().strip().splitlines()
        dump_without_paths = "\n".join(dump_lines[3:])
        self.assertEqual(dump_without_paths, DEFAULT_CONFIG_YAML)

        if sys.platform == "linux":
            import os

            XDG_CONFIG_HOME = os.environ.get(
                "XDG_CONFIG_HOME", os.path.expanduser("~") + ".config"
            )
            XDG_DATA_HOME = os.environ.get(
                "XDG_DATA_HOME", os.path.expanduser("~") + ".local/share"
            )

            dump_only_paths = "\n".join(dump_lines[:3])
            self.assertEqual(
                dump_only_paths,
                DEFAULT_CONFIG_YAML_PATHS.format(
                    XDG_CONFIG_HOME=XDG_CONFIG_HOME,
                    XDG_DATA_HOME=XDG_DATA_HOME,
                ),
            )
