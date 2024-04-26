import argparse
import asyncio
import datetime as dt
from enum import Enum, auto
import os.path
import subprocess as sp
from typing import List, Tuple, Union

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import AnyFormattedText, merge_formatted_text
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.layout import (
    Dimension,
    FormattedTextControl,
    HSplit,
    Layout,
    VSplit,
    Window,
)
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Label
from pytfeeder.defaults import default_config_path
from pytfeeder.feeder import Feeder
from pytfeeder.config import Config
from pytfeeder.models import Channel, Entry
from pytfeeder.storage import Storage


LOCK_FILE = "/tmp/pytfeeder_update.lock"
UPDATE_INVERVAL_MINS = 30
DEFAULT_CHANNELS_FMT = "{new_mark} | {title}"
DEFAULT_ENTRIES_FMT = "{new_mark} | {updated} | {title}"
DEFAULT_NEW_MARK = "[+]"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--channels-fmt",
        default=DEFAULT_CHANNELS_FMT,
        metavar="STR",
        help="channels format (default: %(default)r)",
    )
    parser.add_argument(
        "--entries-fmt",
        default=DEFAULT_ENTRIES_FMT,
        metavar="STR",
        help="entries format (default: %(default)r)",
    )
    parser.add_argument(
        "--new-mark",
        default=DEFAULT_NEW_MARK,
        metavar="STR",
        help="new mark format (default: %(default)r)",
    )
    return parser.parse_args()


def is_update_interval_expired() -> bool:
    def update_lock_file():
        with open(LOCK_FILE, "w") as f:
            f.write(dt.datetime.now().strftime("%s"))

    if not os.path.exists(LOCK_FILE):
        update_lock_file()
        return True

    last_update = dt.datetime.now()
    with open(LOCK_FILE) as f:
        last_update = dt.datetime.fromtimestamp(float(f.read()))
    if last_update < (dt.datetime.now() - dt.timedelta(minutes=UPDATE_INVERVAL_MINS)):
        update_lock_file()
        return True

    return False


def play_video(id: str) -> None:
    sp.Popen(
        [
            "setsid",
            "-f",
            "mpv",
            "https://youtu.be/%s" % id,
            "--ytdl-raw-options=retries=infinite",
        ],
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL,
    )


class PageState(Enum):
    CHANNELS = auto()
    ENTRIES = auto()


Lines = Union[List[Channel], List[Entry]]


class FeederPager:
    def __init__(
        self,
        feeder: Feeder,
        channels_fmt: str = DEFAULT_CHANNELS_FMT,
        entries_fmt: str = DEFAULT_ENTRIES_FMT,
        new_mark: str = DEFAULT_NEW_MARK,
    ) -> None:
        self.feeder = feeder
        self.state = PageState.CHANNELS
        self.channels = [
            Channel("Feed", "feed", have_updates=bool(self.feeder.unviewed_count())),
            *self.feeder.channels,
        ]
        self.entries: List[Entry] = []
        self.selected_line = 0
        self.last_index = -1

        self.channels_fmt = channels_fmt
        self.entries_fmt = entries_fmt
        self.new_mark = new_mark

        self.__toolbar_text = ""
        self.bottom_toolbar = FormattedTextControl(
            text=self._get_toolbar_text,
            focusable=False,
        )
        self.container = HSplit(
            [
                Window(
                    content=FormattedTextControl(
                        text=self._get_formatted_text,
                        focusable=True,
                        key_bindings=self._get_key_bindings(),
                    ),
                    style="class:select-box",
                    cursorline=True,
                ),
                Window(
                    height=Dimension.exact(1),
                    content=self.bottom_toolbar,
                    style="class:toolbar",
                ),
            ]
        )

    @property
    def page_lines(self) -> Lines:
        match self.state:
            case PageState.CHANNELS:
                return self.channels
            case PageState.ENTRIES:
                return self.entries
            case _:
                return []

    def _get_toolbar_text(self) -> str:
        return (
            " %s [h,j,k,l]: navigate, [gg,K]: top, [G,J]: bottom, [q]: quit "
            % self.__toolbar_text
        )

    def _format_entry(self, entry: Entry) -> List[Tuple[str, str]]:
        if entry.is_viewed:
            classname = "entry"
            mark = " " * len(self.new_mark)
        else:
            classname = "new_entry"
            mark = self.new_mark
        updated = entry.updated.strftime("%b %d")
        line = self.entries_fmt.format(
            new_mark=mark, updated=updated, title=entry.title
        )
        return [(f"class:{classname}", line)]

    def _format_channel(self, channel: Channel) -> List[Tuple[str, str]]:
        classname = "entry"
        mark = " " * len(self.new_mark)
        if channel.have_updates:
            classname = "new_entry"
            mark = self.new_mark
        line = self.channels_fmt.format(new_mark=mark, title=channel.title)
        return [(f"class:{classname}", line)]

    def _get_formatted_text(self) -> AnyFormattedText:
        result = []
        for i, entry in enumerate(self.page_lines):
            if i == self.selected_line:
                result.append([("[SetCursorPosition]", "")])
            if isinstance(entry, Entry):
                result.append(self._format_entry(entry))
            elif isinstance(entry, Channel):
                result.append(self._format_channel(entry))
            result.append("\n")

        return merge_formatted_text(result)

    def _get_key_bindings(self) -> KeyBindings:
        kb = KeyBindings()

        @kb.add("k")
        @kb.add("up")
        def _go_up(_) -> None:
            if len(self.page_lines) > 1:
                self.selected_line = (self.selected_line - 1) % len(self.page_lines)

        @kb.add("j")
        @kb.add("down")
        def _go_down(_) -> None:
            if len(self.page_lines) > 1:
                self.selected_line = (self.selected_line + 1) % len(self.page_lines)

        @kb.add("l")
        @kb.add("enter")
        @kb.add("right")
        def _choose_line(event: KeyPressEvent) -> None:
            match self.state:
                case PageState.CHANNELS:
                    if self.selected_line >= len(self.channels):
                        return
                    self.last_index = self.selected_line
                    channel = self.channels[self.selected_line]
                    if channel.channel_id == "feed":
                        self.entries = self.feeder.feed()
                    else:
                        self.entries = self.feeder.channel_feed(channel.channel_id)
                    self.state = PageState.ENTRIES
                    self.selected_line = 0
                    self.__toolbar_text = channel.title
                case PageState.ENTRIES:
                    if self.selected_line >= len(self.entries):
                        return
                    entry_id = self.entries[self.selected_line].id
                    self.feeder.mark_as_viewed(id=entry_id)
                    play_video(entry_id)
                    event.app.exit()

        @kb.add("h")
        @kb.add("left")
        def _back(event) -> None:
            match self.state:
                case PageState.CHANNELS:
                    event.app.exit()
                case PageState.ENTRIES:
                    self.state = PageState.CHANNELS
                    self.entries = []
                    self.selected_line = self.last_index
                    self.last_index = -1
                    self.__toolbar_text = ""

        @kb.add("g", "g")
        @kb.add("K")
        def _go_top(_) -> None:
            self.selected_line = 0

        @kb.add("G")
        @kb.add("J")
        def _go_bottom(_) -> None:
            self.selected_line = 0 if (l := len(self.page_lines)) <= 1 else l - 1

        @kb.add("q")
        def _exit(event) -> None:
            event.app.exit()

        return kb

    def __pt_container__(self) -> HSplit:
        return self.container


if __name__ == "__main__":
    config = Config(default_config_path())
    if not config:
        exit(1)
    if not config.storage_path.parent.exists():
        config.storage_path.parent.mkdir(parents=True)

    args = parse_args()
    feeder = Feeder(config, Storage(config.storage_path))
    pager = FeederPager(feeder, **dict(vars(args)))

    if is_update_interval_expired():
        print("updating...")
        asyncio.run(feeder.sync_entries())

    kb = KeyBindings()

    @kb.add("c-c")
    def _(event):
        event.app.exit()

    Application(
        layout=Layout(VSplit([Label("", width=1), pager])),
        full_screen=True,
        style=Style.from_dict(
            {
                "select-box cursor-line": "nounderline bg:orange fg:black",
                "entry": "white",
                "new_entry": "#ffb71a",
                "toolbar": "bg:orange fg:black",
                "toolbar.text": "",
            },
        ),
        key_bindings=kb,
    ).run()
