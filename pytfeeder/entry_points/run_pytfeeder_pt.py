import datetime as dt
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

from pytfeeder.feeder import Feeder
from pytfeeder.config import Config
from pytfeeder.models import Channel, Entry
from pytfeeder.storage import Storage
from pytfeeder.utils import download_video, download_all, play_video
from pytfeeder.tui.args import parse_args
from pytfeeder.tui.consts import DEFAULT_KEYBINDS
from pytfeeder.tui.updater import Updater
from pytfeeder.tui.props import TuiProps, PageState


Lines = Union[List[Channel], List[Entry]]


class PromptContainer(ConditionalContainer):
    def __init__(self, pager: "App", buffer: Buffer, prompt_text: str = "/"):
        kb = KeyBindings()

        @kb.add("escape")
        @kb.add("c-c")
        def _escape(_) -> None:
            pager.jump_buffer.reset()
            if pager._app_link:
                pager._app_link.layout.focus(pager.main_window)
                pager._app_link.vi_state.input_mode = InputMode.NAVIGATION
                pager._app_link = None

        super(PromptContainer, self).__init__(
            Window(
                BufferControl(
                    buffer=buffer,
                    input_processors=[BeforeInput(prompt_text)],
                    key_bindings=kb,
                ),
                height=1,
            ),
            filter=has_focus(buffer),
        )


class App(TuiProps):
    def __init__(self, feeder: Feeder, updater: Updater) -> None:
        self.feeder = feeder
        super().__init__(self.feeder.config.tui)
        self.updater = updater

        self._set_channels(self.feeder)
        self.refresh_last_update()
        if "{unwatched_count}" in self.c.channels_fmt:
            self.unwatched_method = lambda c_id: self.feeder.unviewed_count(c_id)

        self.entries: List[Entry] = []
        self.is_help_opened = False
        self.help_index = 0
        self.last_index = -1

        self.datetime_fmt = self.feeder.config.datetime_fmt
        self.classnames = {0: "entry", 1: "new_entry"}
        self.max_len_chan_title = max(len(c.title) for c in self.channels)

        self.macros = {
            "f1": self.c.macro1,
            "f2": self.c.macro2,
            "f3": self.c.macro3,
            "f4": self.c.macro4,
        }

        self._app_link: Optional[Application] = None
        self._filter: Optional[str] = None
        self._default_keybinds_fmt = DEFAULT_KEYBINDS
        self._keybinds_fmt = DEFAULT_KEYBINDS
        self._title_fmt = ""

        self.bottom_statusbar = FormattedTextControl(
            text=self._get_statusbar_text,
            focusable=False,
        )
        self.statusbar_window = Window(
            always_hide_cursor=True,
            height=Dimension.exact(1),
            content=self.bottom_statusbar,
            style="class:statusbar",
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

        def filter_handler(buf: Buffer) -> bool:
            if self._app_link:
                self._app_link.layout.focus(self.main_window)
                self._app_link.vi_state.input_mode = InputMode.NAVIGATION
                self._app_link = None
                self._filter = buf.text
                self._title_fmt = "%d found" % len(self.page_lines)
                self._keybinds_fmt = f"[h]: cancel filter, {DEFAULT_KEYBINDS}"
                self.index = 0
            buf.text = ""
            return True

        self.filter_buffer = Buffer(multiline=False, accept_handler=filter_handler)

        self.jump_last_index = None

        def jump_handler(buf: Buffer) -> bool:
            if self._app_link:
                self._app_link.layout.focus(self.main_window)
                self._app_link.vi_state.input_mode = InputMode.NAVIGATION
                self._app_link = None

                try:
                    number = int(buf.text)
                except:
                    return False

                if number > len(self.page_lines) or number < 1:
                    return False

                self.index = number - 1

            buf.text = ""
            return True

        self.jump_buffer = Buffer(multiline=False, accept_handler=jump_handler)

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
                self.statusbar_window,
                PromptContainer(self, self.filter_buffer),
                PromptContainer(self, self.jump_buffer, ":"),
            ]
        )

        if msg := self.updater.status_msg:
            self._status_msg = f"{msg}; "
            self._status_msg_lifetime = time.perf_counter()

    def mark_viewed_all(self) -> None:
        self.selected_data = self.page_lines[self.index]
        if self.page_state == PageState.CHANNELS and isinstance(
            self.selected_data, Channel
        ):
            self.feeder.mark_as_viewed(
                unviewed=all(not c.have_updates for c in self.feeder.channels)
            )
            self._set_channels(self.feeder, channels=self.feeder.update_channels())
        elif self.page_state == PageState.ENTRIES and isinstance(
            self.selected_data, Entry
        ):
            if self.channels[self.last_index].channel_id == "feed":
                unviewed = all(not c.have_updates for c in self.channels)
                self.feeder.mark_as_viewed(unviewed=unviewed)
                for i in range(len(self.channels)):
                    self.channels[i].have_updates = unviewed
                for i in range(len(self.page_lines)):
                    self.page_lines[i].is_viewed = not unviewed  # type: ignore
            else:
                unviewed = not self.channels[self.last_index].have_updates
                self.feeder.mark_as_viewed(
                    channel_id=self.selected_data.channel_id, unviewed=unviewed
                )
                self.channels[self.last_index].have_updates = unviewed
                for i in range(len(self.page_lines)):
                    self.page_lines[i].is_viewed = not unviewed  # type: ignore

    def mark_viewed(self) -> None:
        self.selected_data = self.page_lines[self.index]
        if self.page_state == PageState.CHANNELS:
            if not isinstance(self.selected_data, Channel):
                return
            if self.selected_data.channel_id == "feed":
                return
            unviewed = not self.selected_data.have_updates
            self.feeder.mark_as_viewed(
                channel_id=self.selected_data.channel_id, unviewed=unviewed
            )
            self.selected_data.have_updates = unviewed
        elif self.page_state == PageState.ENTRIES:
            if not isinstance(self.selected_data, Entry):
                return
            unviewed = self.selected_data.is_viewed
            self.feeder.mark_as_viewed(id=self.selected_data.id, unviewed=unviewed)
            self.selected_data.is_viewed = not unviewed
            self.index = (self.index + 1) % len(self.page_lines)

    def set_entries_by_id(self, channel_id: str) -> None:
        if channel_id == "feed":
            self._is_feed_opened = True
            self.entries = self.feeder.feed()
        else:
            self._is_feed_opened = False
            self.entries = self.feeder.channel_feed(channel_id)

    def reset_filter(self) -> None:
        self._filter = None
        self._keybinds_fmt = DEFAULT_KEYBINDS
        if self.page_state == PageState.ENTRIES:
            self._title_fmt = self.channels[self.last_index].title
        elif self.page_state == PageState.CHANNELS:
            self._title_fmt = ""

    @property
    def page_lines(self) -> Lines:
        match self.page_state:
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
            if i == self.index:
                result.append([("[SetCursorPosition]", "")])
            if isinstance(entry, Entry):
                result.append(self._format_entry(i, entry))
            elif isinstance(entry, Channel):
                result.append(self._format_channel(i, entry))
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

    def _get_statusbar_text(self) -> str:
        if self.is_help_opened:
            self._status_msg = ""
            self._title_fmt = "Help"
            self._keybinds_fmt = "[j,Down,k,Up]: navigate, [h,q,Left]: close help"

        if (
            len(self._status_msg) > 0
            and (time.perf_counter() - self._status_msg_lifetime) > 3
        ):
            self._status_msg = ""
            self._status_msg_lifetime = 0

        return " ".join(
            self.c.status_fmt.format(
                msg=self._status_msg,
                index=self._index_fmt,
                title=self._title_fmt,
                keybinds=self._keybinds_fmt,
                last_update=self._last_update,
            ).split()
        )

    @property
    def _index_fmt(self) -> str:
        if self.is_help_opened:
            return ""

        index = self.index + 1
        if len(self.page_lines) == 0:
            index = 0
        num_fmt = f"%{len(str(len(self.page_lines)))}d"
        return "[%s/%s]" % (
            (num_fmt % index),
            (num_fmt % len(self.page_lines)),
        )

    def _entry_index(self, i: int) -> str:
        index = i + 1
        index_len = max(1, len(str(len(self.page_lines))))
        return f"{index:{index_len}d}"

    def _format_entry(self, i: int, entry: Entry) -> List[Tuple[str, str]]:
        line = self.current_entry_format.format(
            index=self._entry_index(i),
            new_mark=self.new_marks[not entry.is_viewed],
            updated=entry.updated.strftime(self.datetime_fmt),
            title=entry.title,
            channel_title=f"{self.feeder.channel_title(entry.channel_id):^{self.max_len_chan_title}s}",
        )
        return [(f"class:{self.classnames[not entry.is_viewed]}", line)]

    def _format_channel(self, i: int, channel: Channel) -> List[Tuple[str, str]]:
        line = self.c.channels_fmt.format(
            index=self._entry_index(i),
            new_mark=self.new_marks[channel.have_updates],
            title=channel.title,
            unwatched_count=self.unwatched_method(channel.channel_id),
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
                self.index = (self.index - 1) % len(self.page_lines)

        @kb.add("j")
        @kb.add("down")
        @kb.add("n")
        @kb.add("tab")
        def _go_down(_) -> None:
            if len(self.page_lines) > 1:
                self.index = (self.index + 1) % len(self.page_lines)

        @kb.add("l")
        @kb.add("enter")
        @kb.add("right")
        def _choose_line(event: KeyPressEvent) -> None:
            if len(self.page_lines) == 0:
                return
            match self.page_state:
                case PageState.CHANNELS:
                    if self.index >= len(self.channels):
                        return
                    if self._filter:
                        if len(self.page_lines) < self.index + 1:
                            return
                        channel = self.page_lines[self.index]
                        last_index = 0
                        for i in range(len(self.channels)):
                            if channel.channel_id == self.channels[i].channel_id:
                                last_index = i
                        self.last_index = last_index

                        self.reset_filter()
                    else:
                        channel = self.channels[self.index]
                        self.last_index = self.index
                    self.set_entries_by_id(channel.channel_id)
                    self.page_state = PageState.ENTRIES
                    self.index = 0
                    self._title_fmt = channel.title
                case PageState.ENTRIES:
                    if self.index >= len(self.entries) or self.index < 0:
                        return
                    self.feeder.mark_as_viewed(id=self.entries[self.index].id)
                    play_video(self.entries[self.index])
                    if not self.entries[self.index].is_viewed:
                        self.mark_viewed()

        @kb.add("h")
        @kb.add("left")
        def _back(event) -> None:
            if self.is_help_opened:
                self.is_help_opened = False
                return

            if self._filter:
                self.reset_filter()
                return

            match self.page_state:
                case PageState.CHANNELS:
                    event.app.exit()
                case PageState.ENTRIES:
                    self.page_state = PageState.CHANNELS
                    self.entries = []
                    self.index = self.last_index
                    self.last_index = -1
                    self._title_fmt = ""

        @kb.add("g", "g")
        @kb.add("home")
        def _go_top(_) -> None:
            self.index = 0

        @kb.add("G")
        @kb.add("end")
        def _go_bottom(_) -> None:
            self.index = max(0, len(self.page_lines) - 1)

        def move_index(prev: bool = False) -> int:
            if prev:
                if self.last_index == 0:
                    return len(self.channels) - 1
                return max(0, self.last_index - 1)
            if self.last_index == len(self.channels) - 1:
                return 0
            return min(len(self.channels) - 1, self.last_index + 1)

        def do_move(prev: bool = False) -> None:
            if not (self.page_state == PageState.ENTRIES and self._filter is None):
                return
            index = move_index(prev)
            self.last_index = index
            self.set_entries_by_id(self.channels[index].channel_id)
            self.index = 0
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
            event.app.layout.focus(self.filter_buffer)
            event.app.vi_state.input_mode = InputMode.INSERT
            self._app_link = event.app

        @kb.add("1")
        @kb.add("2")
        @kb.add("3")
        @kb.add("4")
        @kb.add("5")
        @kb.add("6")
        @kb.add("7")
        @kb.add("8")
        @kb.add("9")
        def _prompt_jump(event: KeyPressEvent) -> None:
            event.app.layout.focus(self.jump_buffer)
            event.app.vi_state.input_mode = InputMode.INSERT
            self.jump_buffer.text = str(event.key_sequence.pop().key)
            self.jump_buffer.cursor_position = 1
            self._app_link = event.app

        @kb.add("f1")
        @kb.add("f2")
        @kb.add("f3")
        @kb.add("f4")
        def _macro(event: KeyPressEvent) -> None:
            if len(self.page_lines) == 0:
                return
            if len(event.key_sequence) != 1:
                return
            if self.page_state != PageState.ENTRIES:
                return

            macro = self.macros.get(key := event.key_sequence.pop().key)
            if not macro or len(macro) == 0:
                self._status_msg = f"Macro {key!r} not found; "
                self._status_msg_lifetime = time.perf_counter()
                return

            self._status_msg = f"Executing macro {key!r}...; "
            self._status_msg_lifetime = time.perf_counter()

            self.selected_data = self.page_lines[self.index]
            if not isinstance(self.selected_data, Entry):
                return

            sp.Popen(
                [macro, self.selected_data.id, self.selected_data.title],
                stdout=sp.DEVNULL,
                stderr=sp.DEVNULL,
            )

        @kb.add("a")
        def _mark_viewed(_) -> None:
            if len(self.page_lines) > 1:
                self.mark_viewed()

        @kb.add("A")
        def _mark_viewed_all(_) -> None:
            self.mark_viewed_all()

        @kb.add("d")
        def _download(_) -> None:
            if self.page_state != PageState.ENTRIES:
                return
            if len(self.page_lines) == 0:
                return

            self.selected_data = self.page_lines[self.index]
            if not isinstance(self.selected_data, Entry):
                return
            download_video(self.selected_data)
            if not self.selected_data.is_viewed:
                self.mark_viewed()

        @kb.add("D")
        def _download_all(_) -> None:
            if self.page_state != PageState.ENTRIES:
                return
            if len(self.page_lines) == 0:
                return
            self.selected_data = self.page_lines[self.index]
            if not isinstance(self.selected_data, Entry):
                return
            entries = [l for l in self.page_lines if l.is_viewed is False]  # type: ignore
            if len(entries) > 0:
                download_all(entries)  # type: ignore
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
            self._status_msg = "reloading...; "
            self._status_msg_lifetime = time.perf_counter()
            event.app.invalidate()
            await self._reload_method()

        return kb

    async def _reload_method(self) -> None:
        after = 0
        before = self.feeder.unviewed_count()
        channel_id = ""
        if self.page_state == PageState.ENTRIES:
            channel_id = self.channels[self.last_index].channel_id
            if channel_id != "feed":
                before = self.feeder.unviewed_count(channel_id)

        try:
            await self.feeder.sync_entries()
        except:
            self._status_msg = "reload failed; "
            return

        self._set_channels(self.feeder, channels=self.feeder.update_channels())
        after = self.feeder.unviewed_count()
        if self.page_state == PageState.ENTRIES:
            self.index = 0
            self.set_entries_by_id(channel_id)
            if channel_id != "feed":
                after = self.feeder.unviewed_count(channel_id)

        new = after - before
        if max(new, 0) > 0:
            self._status_msg = f"{new} new updates; "
        else:
            self._status_msg = "no updates; "
        self._status_msg_lifetime = time.perf_counter()
        self.updater.update_lock_file()
        self.refresh_last_update()

    def refresh_last_update(self) -> None:
        try:
            dt_str = dt.datetime.fromtimestamp(
                float(self.feeder.config.lock_file.read_text())
            )
        except:
            pass
        else:
            self._last_update = dt_str.strftime(self.c.last_update_fmt)

    def __pt_container__(self) -> HSplit:
        return self.container


def main():
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

    kwargs = dict(vars(args))
    feeder.config.parse_args(kwargs)
    feeder.config.tui.parse_args(kwargs)

    updater = Updater(feeder)
    if (
        args.update
        or feeder.config.tui.always_update
        or updater.is_update_interval_expired()
    ):
        print("Updating...")
        if err := updater.update():
            print("Update failed: %s" % err)
            exit(1)

    pager = App(feeder, updater)

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
                    "statusbar": "bg:orange fg:black",
                    "statusbar.text": "",
                },
            ),
            key_bindings=kb,
        ).run()
    except Exception as e:
        print(e)
        exit(1)


if __name__ == "__main__":
    main()
