from enum import Enum, auto
import subprocess as sp
from typing import List, Union

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import merge_formatted_text
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, Layout, VSplit, Window
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Label
from pytfeeder.args import parse_args
from pytfeeder.feeder import Feeder
from pytfeeder.config import Config
from pytfeeder.models import Channel, Entry
from pytfeeder.storage import Storage


def play_video(id: str):
    sp.Popen(
        ["setsid", "-f", "mpv", "https://youtu.be/%s" % id],
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL,
    )


class PageState(Enum):
    CHANNELS = auto()
    ENTRIES = auto()


Lines = Union[List[Channel], List[Entry]]


class FeederPager:
    def __init__(self, feeder: Feeder):
        self.feeder = feeder
        self.state = PageState.CHANNELS
        self.channels = self.feeder.channels
        self.entries: List[Entry] = []
        self.selected_line = 0

        self.container = Window(
            content=FormattedTextControl(
                text=self._get_formatted_text,
                focusable=True,
                key_bindings=self._get_key_bindings(),
            ),
            style="class:select-box",
            cursorline=True,
        )

    def _get_formatted_text(self):
        result = []
        for i, entry in enumerate(self.page_lines):
            if i == self.selected_line:
                result.append([("[SetCursorPosition]", "")])
            result.append(" %s" % entry.title)
            result.append("\n")

        return merge_formatted_text(result)

    @property
    def page_lines(self) -> Lines:
        match self.state:
            case PageState.CHANNELS:
                return self.channels
            case PageState.ENTRIES:
                return self.entries
            case _:
                return []

    def _get_key_bindings(self):
        kb = KeyBindings()

        @kb.add("k")
        @kb.add("up")
        def _go_up(event) -> None:
            self.selected_line = (self.selected_line - 1) % len(self.page_lines)

        @kb.add("j")
        @kb.add("down")
        def _go_down(event) -> None:
            self.selected_line = (self.selected_line + 1) % len(self.page_lines)

        @kb.add("l")
        @kb.add("enter")
        @kb.add("right")
        def _choose_line(event) -> None:
            match self.state:
                case PageState.CHANNELS:
                    if self.selected_line >= len(self.channels):
                        return
                    id = self.channels[self.selected_line].channel_id
                    self.entries = self.feeder.channel_feed(id)
                    self.state = PageState.ENTRIES
                    self.selected_line = 0
                case PageState.ENTRIES:
                    if self.selected_line >= len(self.entries):
                        return
                    play_video(self.entries[self.selected_line].id)
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
                    self.selected_line = 0

        @kb.add("q")
        def _exit(event) -> None:
            event.app.exit()

        return kb

    def __pt_container__(self):
        return self.container


if __name__ == "__main__":
    args = parse_args()
    config = Config(args.config_file)
    if not config:
        exit(1)
    db_file = args.cache_dir.joinpath("test.db")
    feeder = Feeder(config, Storage(db_file))

    kb = KeyBindings()

    @kb.add("c-c")
    def _(event):
        event.app.exit()

    Application(
        layout=Layout(VSplit([Label("", width=1), FeederPager(feeder)])),
        full_screen=True,
        style=Style.from_dict(
            {"select-box cursor-line": "nounderline bg:orange fg:black"}
        ),
        key_bindings=kb,
    ).run()
