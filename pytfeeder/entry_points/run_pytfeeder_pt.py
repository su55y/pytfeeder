import logging
import subprocess as sp
import sys

# added in python 3.12
# https://docs.python.org/3/library/typing.html#typing.override
if sys.version_info < (3, 12):
    from typing_extensions import override
else:
    from typing import override


from prompt_toolkit.filters import has_focus
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import (
    AnyFormattedText,
    OneStyleAndTextTuple,
    merge_formatted_text,
)
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

from pytfeeder import Config, Feeder, Storage, utils, __version__
from pytfeeder.logger import init_logger
from pytfeeder.models import Channel, Entry
from pytfeeder.tui import args as tui_args
from pytfeeder.tui.props import TuiProps, PageState


Lines = list[Channel] | list[Entry]


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
    def __init__(self, feeder: Feeder) -> None:
        super().__init__(feeder)

        self._app_link: Application | None = None
        self.classnames = {0: "entry", 1: "new_entry"}
        self.entries: list[Entry] = []
        self.filter_text = ""
        self.help_index = 0
        self.is_help_opened = False
        self.last_index = -1
        self.macros = {
            "f1": self.c.macro1,
            "f2": self.c.macro2,
            "f3": self.c.macro3,
            "f4": self.c.macro4,
        }
        self.status_title = ""

        self.bottom_statusbar = FormattedTextControl(
            text=self._get_statusbar_text,
            focusable=False,
        )
        self.statusbar_window = Window(
            always_hide_cursor=True,
            height=Dimension.exact(self.statusbar_height),
            content=self.bottom_statusbar,
            style="class:statusbar",
        )

        self.main_window = Window(
            always_hide_cursor=True,
            content=FormattedTextControl(
                text=self._get_formatted_text,
                focusable=True,
                key_bindings=self._main_keybindings,
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
                self.filter_text = buf.text
                self.is_filtered = True
                self.index = 0
            buf.text = ""
            return True

        self.filter_buffer = Buffer(multiline=False, accept_handler=filter_handler)

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
                key_bindings=self._help_keybindings,
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

    def __pt_container__(self) -> HSplit:
        return self.container

    @property
    def page_lines(self) -> Lines:
        if self.page_state == PageState.CHANNELS:
            if self.is_filtered and self.filter_text:
                return [
                    channel
                    for channel in self.channels
                    if self.filter_text.lower() in channel.title.lower()
                ]
            return self.channels
        elif self.page_state == PageState.ENTRIES:
            if self.is_filtered and self.filter_text:
                return [
                    entry
                    for entry in self.entries
                    if self.filter_text.lower() in entry.title.lower()
                ]
            return self.entries
        return []

    def format_channel(self, i: int, channel: Channel) -> list[OneStyleAndTextTuple]:
        line = self.c.channels_fmt.format(
            index=self.format_line_index(i + 1),
            new_mark=self.new_marks[channel.have_updates],
            title=channel.title,
            unwatched_count=self.unwatched_method(channel.channel_id),
        )
        return [(f"class:{self.classnames[channel.have_updates]}", line)]

    def format_entry(self, i: int, entry: Entry) -> list[OneStyleAndTextTuple]:
        line = self.current_entry_format.format(
            index=self.format_line_index(i + 1),
            new_mark=self.new_marks[not entry.is_viewed],
            published=entry.published.strftime(self.c.datetime_fmt),
            title=entry.title,
            channel_title=self.channel_title(entry.channel_id),
        )
        return [(f"class:{self.classnames[not entry.is_viewed]}", line)]

    def format_line_index(self, i: int) -> str:
        index_len = max(1, len(str(len(self.page_lines))))
        return f"{i:{index_len}d}"

    def _get_formatted_text(self) -> AnyFormattedText:
        result: list[AnyFormattedText] = []
        for i, line in enumerate(self.page_lines):
            if i == self.index:
                result.append([("[SetCursorPosition]", "")])
            if isinstance(line, Entry):
                result.append(self.format_entry(i, line))
            elif isinstance(line, Channel):
                result.append(self.format_channel(i, line))
            result.append("\n")

        return merge_formatted_text(result)

    def _get_formatted_help_text(self) -> AnyFormattedText:
        result: list[AnyFormattedText] = []
        for i, line in enumerate(self.help_lines):
            if i == self.help_index:
                result.append([("[SetCursorPosition]", "")])
            result.append([(f"class:{self.classnames[0]}", line)])
            result.append("\n")

        return merge_formatted_text(result)

    def _get_statusbar_text(self) -> str:
        if self.is_help_opened:
            return self.help_status

        title = self.status_title
        if self.is_filtered:
            title = "%d found" % len(self.page_lines)

        return " ".join(
            self.c.status_fmt.format(
                msg=self.status_msg,
                index=self.status_index(lines_count=len(self.page_lines)),
                title=title,
                keybinds=self.status_keybinds,
                last_update=self.status_last_update,
            ).split()
        )

    def mark_as_watched_all(self) -> None:
        self.selected_data = self.page_lines[self.index]
        if self.page_state == PageState.CHANNELS and isinstance(
            self.selected_data, Channel
        ):
            self.feeder.mark_as_watched(
                unwatched=all(not c.have_updates for c in self.feeder.channels)
            )
            self.update_channels()
        elif self.page_state == PageState.ENTRIES and isinstance(
            self.selected_data, Entry
        ):
            if self.channels[self.last_index].channel_id == "feed":
                unwatched = all(not c.have_updates for c in self.channels)
                self.feeder.mark_as_watched(unwatched=unwatched)
                self.is_channels_outdated = True
                for i in range(len(self.channels)):
                    self.channels[i].have_updates = unwatched
                for i in range(len(self.page_lines)):
                    self.page_lines[i].is_viewed = not unwatched  # type: ignore
            else:
                unwatched = not self.channels[self.last_index].have_updates
                self.feeder.mark_as_watched(
                    channel_id=self.selected_data.channel_id, unwatched=unwatched
                )
                self.is_channels_outdated = True
                self.channels[self.last_index].have_updates = unwatched
                for i in range(len(self.page_lines)):
                    self.page_lines[i].is_viewed = not unwatched  # type: ignore

    def mark_as_watched(self) -> None:
        self.selected_data = self.page_lines[self.index]
        if self.page_state == PageState.CHANNELS:
            if not isinstance(self.selected_data, Channel):
                return
            if self.selected_data.channel_id == "feed":
                return
            unwatched = not self.selected_data.have_updates
            self.feeder.mark_as_watched(
                channel_id=self.selected_data.channel_id, unwatched=unwatched
            )
            self.is_channels_outdated = True
            self.selected_data.have_updates = unwatched
        elif self.page_state == PageState.ENTRIES:
            if not isinstance(self.selected_data, Entry):
                return
            unwatched = self.selected_data.is_viewed
            self.feeder.mark_as_watched(id=self.selected_data.id, unwatched=unwatched)
            self.is_channels_outdated = True
            self.selected_data.is_viewed = not unwatched
            self.index = (self.index + 1) % len(self.page_lines)

    @override
    def get_parent_channel_id(self) -> str | None:
        if self.last_index > -1 and self.last_index < len(self.channels):
            return self.channels[self.last_index].channel_id
        return None

    @override
    def reload_lines(self, channel_id: str | None = None) -> None:
        if self.page_state == PageState.ENTRIES and channel_id:
            self.index = 0
            self.set_entries_by_id(channel_id)

    def reset_filter(self) -> None:
        self.filter_text = ""
        self.is_filtered = False
        if self.page_state == PageState.ENTRIES:
            self.status_title = self.channels[self.last_index].title
        elif self.page_state == PageState.CHANNELS:
            self.status_title = ""

    def set_entries_by_id(self, channel_id: str) -> None:
        if channel_id == "feed":
            self._is_feed_opened = True
            self.entries = self.feed()
        else:
            self._is_feed_opened = False
            self.entries = self.channel_feed(channel_id)

    @property
    def _help_keybindings(self) -> KeyBindings:
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
            self.status_title = ""

        return kb

    @property
    def _main_keybindings(self) -> KeyBindings:
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
                    if self.is_filtered:
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
                    self.status_title = channel.title
                case PageState.ENTRIES:
                    if self.index >= len(self.entries) or self.index < 0:
                        return
                    self.feeder.mark_as_watched(id=self.entries[self.index].id)
                    utils.play_video(self.entries[self.index])
                    if not self.entries[self.index].is_viewed:
                        self.mark_as_watched()

        @kb.add("h")
        @kb.add("left")
        def _back(event) -> None:
            if self.is_help_opened:
                self.is_help_opened = False
                return

            if self.is_channels_outdated:
                self.update_channels()

            if self.is_filtered:
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
                    self.status_title = ""

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
            if not (self.page_state == PageState.ENTRIES and not self.is_filtered):
                return
            index = move_index(prev)
            self.last_index = index
            self.set_entries_by_id(self.channels[index].channel_id)
            self.index = 0
            self.status_title = self.channels[index].title

        @kb.add("J")
        def _go_next(_) -> None:
            do_move()

        @kb.add("K")
        def _go_prev(_) -> None:
            do_move(prev=True)

        @kb.add("f")
        def _follow(_) -> None:
            if (
                self.page_state != PageState.ENTRIES
                or self.last_index != 0
                or not self._is_feed_opened
                or self.is_filtered
            ):
                return
            # find new last_index value
            new_last_index = -1
            for i in range(len(self.channels)):
                if self.entries[self.index].channel_id == self.channels[i].channel_id:
                    new_last_index = i
                    break
            if new_last_index < 1:
                return
            self.set_entries_by_id(self.entries[self.index].channel_id)
            self.last_index = new_last_index
            self.index = 0
            self.status_title = self.channels[self.last_index].title

        @kb.add("s")
        def _toggle_status_visability(_) -> None:
            self.c.hide_statusbar = not self.c.hide_statusbar
            self.statusbar_window.height = Dimension.exact(self.statusbar_height)

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
                self.status_msg = f"macro {key!r} not found"
                return

            self.status_msg = f"executing {macro!r}..."

            self.selected_data = self.page_lines[self.index]
            if not isinstance(self.selected_data, Entry):
                return

            sp.Popen(
                [macro, self.selected_data.id, self.selected_data.title],
                stdout=sp.DEVNULL,
                stderr=sp.DEVNULL,
            )

        @kb.add("a")
        def _mark_as_watched(_) -> None:
            if len(self.page_lines) > 1:
                self.mark_as_watched()

        @kb.add("A")
        def _mark_as_watched_all(_) -> None:
            self.mark_as_watched_all()

        @kb.add("d")
        def _download(_) -> None:
            if self.page_state != PageState.ENTRIES:
                return
            if len(self.page_lines) == 0:
                return

            self.selected_data = self.page_lines[self.index]
            if not isinstance(self.selected_data, Entry):
                return
            # FIXME: will fail if tsp or notify-send not an executable
            utils.download_video(self.selected_data, self.c.download_output)
            if not self.selected_data.is_viewed:
                self.mark_as_watched()

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
                utils.download_all(entries, self.c.download_output)  # type: ignore
                self.mark_as_watched_all()

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
            self.status_msg = "updating..."
            event.app.invalidate()
            await self.sync_and_reload()

        return kb


def main():
    args = tui_args.parse_args()
    config_path = args.config
    config = Config(config_file=config_path)
    config.tui.update(vars(args))

    if not config.storage_path.parent.exists():
        config.storage_path.parent.mkdir(parents=True)

    init_logger(config.logger)

    feeder = Feeder(config, Storage(config.storage_path))
    if len(feeder.channels) == 0:
        print(f"No channels found in config {config_path}")
        sys.exit(0)

    pager = App(feeder)

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
        ).run(set_exception_handler=False)
    except Exception as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
