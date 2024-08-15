import argparse
import asyncio
import datetime as dt
from enum import Enum, auto
import os.path
import subprocess as sp
import time
from typing import List, Optional, Tuple, Union

from prompt_toolkit.filters import has_focus
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import AnyFormattedText, merge_formatted_text
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.key_binding.vi_state import InputMode
from prompt_toolkit.layout import (
    BufferControl,
    ConditionalContainer,
    Dimension,
    FormattedTextControl,
    HSplit,
    Layout,
    VSplit,
    Window,
)
from prompt_toolkit.layout.processors import BeforeInput
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
DEFAULT_KEYBINDS = "[h,j,k,l]: navigate, [q]: quit, [?]: help"
DEFAULT_STATUS_FMT = "{msg}{index} {title} {keybinds}"
DEFAULT_DATETIME_FMT = "%b %d"
OPTIONS_DESCRIPTION = """
channels-fmt keys:
    {new_mark}      - new-mark if have updates, otherwise `' '*len(new_mark)`
    {title}         - title of the channel

entries-fmt keys:
    {new_mark}      - new-mark if have updates, otherwise `' '*len(new_mark)`
    {title}         - title of the entry
    {updated}       - updated in `--datetime-fmt` format (rss `updated` value or fetch date)
    {channel_title} - title of the channel
"""
HELP_KEYBINDINGS = [
    ("h, Left", "Return to previous screen/Quit"),
    ("j, Down, Tab, n", "Move to the next entry"),
    ("k, Up, S-Tab, p", "Move to the previous entry"),
    ("l, Right, Enter", "Open feed/entry"),
    ("gg, Home", "Move to the top of list"),
    ("G, End", "Move to the bottom of list"),
    ("J", "Move to the next feed"),
    ("K", "Move to the prev feed"),
    ("a", "Mark entry/feed viewed"),
    ("A", "Mark all enties/feeds viewed"),
    ("r", "Reload/sync feeds"),
    ("/", "Open filter"),
    ("h", "Cancel filter"),
    ("c", "Clear screen"),
    ("q", "Quit"),
]


def format_keybindings() -> list[str]:
    max_keys_w = max(len(keys) for keys, _ in HELP_KEYBINDINGS)
    tab = " " * 4
    return [f"{tab}{keys:<{max_keys_w}}{tab}{desc}" for keys, desc in HELP_KEYBINDINGS]


def parse_args() -> argparse.Namespace:
    def format_epilog() -> str:
        keybinds_str = "\n".join(format_keybindings())
        return f"{OPTIONS_DESCRIPTION}\n\nkeybindings:\n{keybinds_str}\n"

    parser = argparse.ArgumentParser(
        epilog=format_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--channels-fmt",
        default=DEFAULT_CHANNELS_FMT,
        metavar="STR",
        help="channels format (default: %(default)r)",
    )
    parser.add_argument(
        "-c",
        "--config",
        metavar="PATH",
        default=default_config_path(),
        help="config path (default: %(default)s)",
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
    parser.add_argument(
        "--status-fmt",
        default=DEFAULT_STATUS_FMT,
        metavar="STR",
        help="status bar format (default: %(default)r)",
    )
    parser.add_argument(
        "--datetime-fmt",
        default=DEFAULT_DATETIME_FMT,
        metavar="STR",
        help="entries `{updated}` datetime format (default: %(default)r)",
    )
    parser.add_argument(
        "--hide-feed", action="store_true", help="Hide 'Feed' in channels list"
    )
    parser.add_argument(
        "-U", "--no-update", action="store_false", help="Disable update on startup"
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


class CommandLine(ConditionalContainer):
    def __init__(self, pager: "FeederPager"):
        super(CommandLine, self).__init__(
            Window(
                BufferControl(
                    buffer=pager.command_buffer, input_processors=[BeforeInput("/")]
                ),
                height=1,
            ),
            filter=has_focus(pager.command_buffer),
        )


class FeederPager:
    def __init__(
        self,
        feeder: Feeder,
        channels_fmt: str = DEFAULT_CHANNELS_FMT,
        entries_fmt: str = DEFAULT_ENTRIES_FMT,
        new_mark: str = DEFAULT_NEW_MARK,
        status_fmt: str = DEFAULT_STATUS_FMT,
        datetime_fmt: str = DEFAULT_DATETIME_FMT,
        hide_feed: bool = False,
        **_,
    ) -> None:
        self.feeder = feeder

        self.hide_feed = hide_feed
        self.channels = list()
        self._set_channels()

        self.entries: List[Entry] = []
        self.help_lines = list(map(lambda s: s.lstrip(), format_keybindings()))
        self.is_help_opened = False
        self.state = PageState.CHANNELS
        self.selected_line = 0
        self.help_index = 0
        self.last_index = -1

        self.channels_fmt = channels_fmt
        self.entries_fmt = entries_fmt
        self.datetime_fmt = datetime_fmt
        self.new_marks = {0: " " * len(new_mark), 1: new_mark}
        self.classnames = {0: "entry", 1: "new_entry"}
        self.max_len_chan_title = max(len(c.title) for c in self.channels)

        self._command_line_app_link: Optional[Application] = None
        self._filter: Optional[str] = None

        self._status_fmt = status_fmt
        self._status_msg = ""
        self._status_msg_time = 0
        self._default_keybinds_fmt = DEFAULT_KEYBINDS
        self._keybinds_fmt = DEFAULT_KEYBINDS
        self._title_fmt = ""

        self.bottom_toolbar = FormattedTextControl(
            text=self._get_toolbar_text,
            focusable=False,
        )
        self.toolbar_window = Window(
            always_hide_cursor=True,
            height=Dimension.exact(1),
            content=self.bottom_toolbar,
            style="class:toolbar",
        )

        self.main_window = Window(
            always_hide_cursor=True,
            content=FormattedTextControl(
                text=self._get_formatted_text,
                focusable=True,
                key_bindings=self._get_key_bindings(),
            ),
            style="class:select-box",
            cursorline=True,
            z_index=1,
        )

        def command_line_handler(buf: Buffer) -> bool:
            if self._command_line_app_link:
                self._command_line_app_link.layout.focus(self.main_window)
                self._command_line_app_link.vi_state.input_mode = InputMode.NAVIGATION
                self._command_line_app_link = None
                self._filter = buf.text
                self._title_fmt = "%d found" % len(self.page_lines)
                self._keybinds_fmt = f"[h]: cancel filter, {DEFAULT_KEYBINDS}"
            buf.text = ""
            return True

        self.command_buffer = Buffer(
            multiline=False, accept_handler=command_line_handler
        )

        self.help_window = Window(
            always_hide_cursor=True,
            content=FormattedTextControl(
                text=self._get_formatted_help_text,
                focusable=True,
                key_bindings=self._get_help_bindings(),
            ),
            height=0,
            style="class:entry",
            z_index=0,
        )
        self.container = HSplit(
            [
                self.main_window,
                self.help_window,
                self.toolbar_window,
                CommandLine(self),
            ]
        )

    def _set_channels(self, channels: List[Channel] = list()) -> None:
        if channels:
            self.feeder.channels = channels

        if self.hide_feed:
            self.channels = self.feeder.channels
        else:
            feed_channel = Channel(
                title="Feed",
                channel_id="feed",
                have_updates=bool(self.feeder.unviewed_count()),
            )
            self.channels = [feed_channel, *self.feeder.channels]

    def mark_viewed_all(self) -> None:
        self.selected_data = self.page_lines[self.selected_line]
        if self.state == PageState.CHANNELS:
            if not isinstance(self.selected_data, Channel):
                return
            for i in range(len(self.channels)):
                self.channels[i].have_updates = False
        elif self.state == PageState.ENTRIES:
            if not isinstance(self.selected_data, Entry):
                return
            if self.channels[self.last_index].channel_id == "feed":
                self.feeder.mark_as_viewed()
                for i in range(len(self.channels)):
                    self.channels[i].have_updates = False
                for i in range(len(self.page_lines)):
                    self.page_lines[i].is_viewed = True  # type: ignore
            else:
                self.feeder.mark_as_viewed(channel_id=self.selected_data.channel_id)
                self.channels[self.last_index].have_updates = False
                for i in range(len(self.page_lines)):
                    self.page_lines[i].is_viewed = True  # type: ignore

    def mark_viewed(self) -> None:
        self.selected_data = self.page_lines[self.selected_line]
        if self.state == PageState.CHANNELS:
            if not isinstance(self.selected_data, Channel):
                return
            if self.selected_data.channel_id == "feed":
                return
            self.feeder.mark_as_viewed(channel_id=self.selected_data.channel_id)
            self.selected_data.have_updates = False
        elif self.state == PageState.ENTRIES:
            if not isinstance(self.selected_data, Entry):
                return
            self.feeder.mark_as_viewed(id=self.selected_data.id)
            self.selected_data.is_viewed = True

    def set_entries_by_id(self, channel_id: str) -> None:
        if channel_id == "feed":
            self.entries = self.feeder.feed()
        else:
            self.entries = self.feeder.channel_feed(channel_id)

    @property
    def page_lines(self) -> Lines:
        match self.state:
            case PageState.CHANNELS:
                if self._filter:
                    return [
                        c
                        for c in self.channels
                        if self._filter.lower() in c.title.lower()
                    ]
                return self.channels
            case PageState.ENTRIES:
                if self._filter:
                    return [
                        e
                        for e in self.entries
                        if self._filter.lower() in e.title.lower()
                    ]
                return self.entries
            case _:
                return []

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

    def _get_formatted_help_text(self) -> AnyFormattedText:
        result = []
        for i, line in enumerate(self.help_lines):
            if i == self.help_index:
                result.append([("[SetCursorPosition]", "")])
            result.append([(f"class:{self.classnames[0]}", line)])
            result.append("\n")

        return merge_formatted_text(result)

    def _get_toolbar_text(self) -> str:
        if self.is_help_opened:
            self._status_msg = ""
            self._title_fmt = "Help"
            self._keybinds_fmt = "[j,Down,k,Up]: navigate, [h,q,Left]: close help"

        if (
            len(self._status_msg) > 0
            and (time.perf_counter() - self._status_msg_time) > 3
        ):
            self._status_msg = ""
            self._status_msg_time = 0

        return " ".join(
            self._status_fmt.format(
                msg=self._status_msg,
                index=self._index_fmt,
                title=self._title_fmt,
                keybinds=self._keybinds_fmt,
            ).split()
        )

    @property
    def _index_fmt(self) -> str:
        if self.is_help_opened:
            return ""

        index = self.selected_line + 1
        if len(self.page_lines) == 0:
            index = 0
        num_fmt = f"%{len(str(len(self.page_lines)))}d"
        return "[%s/%s]" % (
            (num_fmt % index),
            (num_fmt % len(self.page_lines)),
        )

    def _format_entry(self, entry: Entry) -> List[Tuple[str, str]]:
        line = self.entries_fmt.format(
            new_mark=self.new_marks[not entry.is_viewed],
            updated=entry.updated.strftime(self.datetime_fmt),
            title=entry.title,
            channel_title=f"{self.feeder.channel_title(entry.channel_id):^{self.max_len_chan_title}s}",
        )
        return [(f"class:{self.classnames[not entry.is_viewed]}", line)]

    def _format_channel(self, channel: Channel) -> List[Tuple[str, str]]:
        line = self.channels_fmt.format(
            new_mark=self.new_marks[channel.have_updates], title=channel.title
        )
        return [(f"class:{self.classnames[channel.have_updates]}", line)]

    def _get_help_bindings(self) -> KeyBindings:
        kb = KeyBindings()

        @kb.add("k")
        @kb.add("up")
        @kb.add("p")
        @kb.add("s-tab")
        def _go_up(_) -> None:
            if len(self.help_lines) > 1:
                self.help_index = (self.help_index - 1) % len(self.help_lines)

        @kb.add("j")
        @kb.add("down")
        @kb.add("n")
        @kb.add("tab")
        def _go_down(_) -> None:
            if len(self.help_lines) > 1:
                self.help_index = (self.help_index + 1) % len(self.help_lines)

        @kb.add("b")
        @kb.add("h")
        @kb.add("left")
        @kb.add("q")
        @kb.add("?")
        def _back(event: KeyPressEvent) -> None:
            self.is_help_opened = False
            self.help_window.height = 0
            self.main_window.height = self.container.height
            event.app.layout.reset()
            event.app.layout.focus(self.main_window)
            self._keybinds_fmt = self._default_keybinds_fmt
            self._title_fmt = ""

        return kb

    def _get_key_bindings(self) -> KeyBindings:
        kb = KeyBindings()

        @kb.add("k")
        @kb.add("up")
        @kb.add("p")
        @kb.add("s-tab")
        def _go_up(_) -> None:
            if len(self.page_lines) > 1:
                self.selected_line = (self.selected_line - 1) % len(self.page_lines)

        @kb.add("j")
        @kb.add("down")
        @kb.add("n")
        @kb.add("tab")
        def _go_down(_) -> None:
            if len(self.page_lines) > 1:
                self.selected_line = (self.selected_line + 1) % len(self.page_lines)

        @kb.add("l")
        @kb.add("enter")
        @kb.add("right")
        def _choose_line(event: KeyPressEvent) -> None:
            if len(self.page_lines) == 0:
                return
            match self.state:
                case PageState.CHANNELS:
                    if self.selected_line >= len(self.channels):
                        return
                    self.last_index = self.selected_line
                    channel = self.channels[self.selected_line]
                    self.set_entries_by_id(channel.channel_id)
                    self.state = PageState.ENTRIES
                    self.selected_line = 0
                    self._title_fmt = channel.title
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
            if self.is_help_opened:
                self.is_help_opened = False
                return

            if self._filter:
                self._filter = None
                self._keybinds_fmt = DEFAULT_KEYBINDS
                if self.state is PageState.ENTRIES:
                    self._title_fmt = self.channels[self.last_index].title
                elif self.state is PageState.CHANNELS:
                    self._title_fmt = ""
                return
            match self.state:
                case PageState.CHANNELS:
                    event.app.exit()
                case PageState.ENTRIES:
                    self.state = PageState.CHANNELS
                    self.entries = []
                    self.selected_line = self.last_index
                    self.last_index = -1
                    self._title_fmt = ""

        @kb.add("g", "g")
        @kb.add("home")
        def _go_top(_) -> None:
            self.selected_line = 0

        @kb.add("G")
        @kb.add("end")
        def _go_bottom(_) -> None:
            self.selected_line = max(0, len(self.page_lines) - 1)

        def move_index(prev: bool = False) -> int:
            if prev:
                if self.last_index == 0:
                    return len(self.channels) - 1
                return max(0, self.last_index - 1)
            if self.last_index == len(self.channels) - 1:
                return 0
            return min(len(self.channels) - 1, self.last_index + 1)

        def do_move(prev: bool = False) -> None:
            if not (self.state == PageState.ENTRIES and self._filter is None):
                return
            index = move_index(prev)
            self.last_index = index
            self.set_entries_by_id(self.channels[index].channel_id)
            self.selected_line = 0
            self._title_fmt = self.channels[index].title

        @kb.add("J")
        def _go_next(_) -> None:
            do_move()

        @kb.add("K")
        def _go_prev(_) -> None:
            do_move(prev=True)

        @kb.add("q")
        def _exit(event) -> None:
            event.app.exit()

        @kb.add("/")
        def _prompt_search(event: KeyPressEvent) -> None:
            event.app.layout.focus(self.command_buffer)
            event.app.vi_state.input_mode = InputMode.INSERT
            self._command_line_app_link = event.app

        @kb.add("a")
        def _mark_viewed(_) -> None:
            self.mark_viewed()

        @kb.add("A")
        def _mark_viewed_all(_) -> None:
            self.mark_viewed_all()

        @kb.add("?")
        def _open_help(event: KeyPressEvent) -> None:
            if not self.is_help_opened:
                self.is_help_opened = True
                event.app.layout.reset()
                self.main_window.height = 0
                self.help_window.reset()
                self.help_window.height = self.container.height
                event.app.layout.focus(self.help_window)
            else:
                self.is_help_opened = False
                event.app.layout.focus(self.main_window)

        @kb.add("r")
        async def _reload(event: KeyPressEvent) -> None:
            after = 0
            before = 0
            channel_id = ""
            self._status_msg = "reloading...; "
            event.app._redraw()
            if self.state == PageState.ENTRIES:
                channel_id = self.channels[self.last_index].channel_id
                if channel_id != "feed":
                    before = self.feeder.unviewed_count(channel_id)
                else:
                    before = self.feeder.unviewed_count()

            try:
                await self.feeder.sync_entries()
            except:
                self._status_msg = "reload failed; "
                return

            self._set_channels(self.feeder.update_channels())
            if self.state == PageState.CHANNELS:
                after = self.feeder.unviewed_count()
            elif self.state == PageState.ENTRIES:
                self.selected_line = 0
                self.set_entries_by_id(channel_id)
                if channel_id == "feed":
                    after = self.feeder.unviewed_count()
                else:
                    after = self.feeder.unviewed_count(channel_id)

            new = after - before
            if max(new, 0) > 0:
                self._status_msg = f"{new} new updates; "
            else:
                self._status_msg = "no updates; "
            self._status_msg_time = time.perf_counter()

        return kb

    def __pt_container__(self) -> HSplit:
        return self.container


if __name__ == "__main__":
    args = parse_args()
    config_path = args.config
    config = Config(config_path)
    if not config:
        exit(1)
    if not config.storage_path.parent.exists():
        config.storage_path.parent.mkdir(parents=True)

    feeder = Feeder(config, Storage(config.storage_path))

    if len(feeder.channels) == 0:
        print(f"No channels found in config {config_path}")
        exit(0)

    if args.no_update and is_update_interval_expired():
        print("updating...")
        try:
            asyncio.run(feeder.sync_entries())
        except Exception as e:
            print("Update failed: %s" % e)

    pager = FeederPager(feeder, **dict(vars(args)))

    kb = KeyBindings()

    @kb.add("c-c")
    def _(event):
        event.app.exit()

    try:
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
    except Exception as e:
        print(e)
        exit(1)
