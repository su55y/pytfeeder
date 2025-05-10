import subprocess as sp
import sys

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import has_focus
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
from pytfeeder.tui import args as tui_args, ConfigTUI
from pytfeeder.tui.props import TuiProps, PageState, Line


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
        self.filter_text = ""
        self.help_index = 0
        self.is_help_opened = False
        self.__lines_backup: list[Line] = list()
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
                condition = lambda v: buf.text.lower() in v.data.title.lower()
                self.lines = list(filter(condition, self.__lines_backup))
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

                if number > len(self.lines) or number < 1:
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

    def format_channel(self, i: int, channel: Channel) -> list[OneStyleAndTextTuple]:
        line = self.c.channels_fmt.format(
            index=self.format_line_index(i + 1),
            new_mark=self.new_marks[channel.have_updates],
            title=channel.title,
            unwatched=channel.unwatched_count,
            total=channel.entries_count,
            unwatched_total=self.format_unwatched_total_key(channel),
        )
        classname = self.classnames[channel.have_updates]
        if channel.entries_count == 0:
            classname = "empty"
        return [(f"class:{classname}", line)]

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
        index_len = max(1, len(str(len(self.lines))))
        return f"{i:{index_len}d}"

    def _get_formatted_text(self) -> AnyFormattedText:
        result: list[AnyFormattedText] = []
        for i, line in enumerate(self.lines):
            if i == self.index:
                result.append([("[SetCursorPosition]", "")])
            if isinstance(line.data, Entry):
                result.append(self.format_entry(i, line.data))
            elif isinstance(line.data, Channel):
                result.append(self.format_channel(i, line.data))
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
            title = "%d found" % len(self.lines)

        return " ".join(
            self.c.status_fmt.format(
                msg=self.status_msg,
                index=self.status_index(lines_count=len(self.lines)),
                title=title,
                keybinds=self.status_keybinds,
                last_update=self.status_last_update,
            ).split()
        )

    def reset_filter(self) -> None:
        self.filter_text = ""
        self.is_filtered = False
        self.lines = self.__lines_backup.copy()
        self.__lines_backup = list()
        self.status_title = ""
        if self.page_state == PageState.ENTRIES:
            self.status_title = self.channels[self.parent_index].title

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
        def _go_back(event: KeyPressEvent) -> None:
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
            if len(self.lines) > 1:
                self.index = (self.index - 1) % len(self.lines)

        @kb.add("j")
        @kb.add("down")
        @kb.add("n")
        @kb.add("tab")
        def _go_down(_) -> None:
            if len(self.lines) > 1:
                self.index = (self.index + 1) % len(self.lines)

        @kb.add("l")
        @kb.add("enter")
        @kb.add("right")
        def _enter_line(event: KeyPressEvent) -> None:
            if len(self.lines) == 0:
                return
            if self.index not in range(len(self.lines)):
                raise Exception(f"{self.index=} out of range 0-{len(self.lines)}")

            if self.page_state == PageState.ENTRIES:
                entry = self.lines[self.index].data
                if not isinstance(entry, Entry):
                    raise Exception(f"Unexpected entry type {type(entry) = !r}")

                utils.play_video(entry)
                if not entry.is_viewed:
                    self.mark_as_watched()
                return

            channel = self.lines[self.index].data
            if not isinstance(channel, Channel):
                raise Exception(f"Unexpected channel type {type(channel) = !r}")

            if channel.entries_count == 0:
                return

            if self.is_filtered:
                self.parent_index = self.find_channel_index_by_id(channel.channel_id)
                self.reset_filter()
            else:
                self.parent_index = self.index
            self.lines = self.get_lines_by_id(channel.channel_id)
            self.page_state = PageState.ENTRIES
            self.index = 0
            self.status_title = channel.title

        @kb.add("h")
        @kb.add("left")
        def _go_back(event) -> None:
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
                    self.lines = list(map(Line, self.channels))
                    self.index = self.parent_index
                    self.parent_index = -1
                    self.status_title = ""

        @kb.add("g", "g")
        @kb.add("home")
        def _go_top(_) -> None:
            self.index = 0

        @kb.add("G")
        @kb.add("end")
        def _go_bottom(_) -> None:
            self.index = max(0, len(self.lines) - 1)

        @kb.add("J")
        def _go_next(_) -> None:
            if self.handle_move(gravity=1):
                self.status_title = self.channels[self.parent_index].title

        @kb.add("K")
        def _go_prev(_) -> None:
            if self.handle_move(gravity=-1):
                self.status_title = self.channels[self.parent_index].title

        @kb.add("f")
        def _follow(_) -> None:
            if (
                self.page_state != PageState.ENTRIES
                or not self._is_feed_opened
                or self.parent_index != 0
            ):
                return

            channel_id = self.lines[self.index].data.channel_id
            self.parent_index = self.find_channel_index_by_id(channel_id)
            self.is_filtered = False
            self.lines = self.get_lines_by_id(channel_id)
            self.index = 0
            self.status_title = self.channels[self.parent_index].title

        @kb.add("s")
        def _toggle_status_visability(_) -> None:
            self.c.hide_statusbar = not self.c.hide_statusbar
            self.statusbar_window.height = Dimension.exact(self.statusbar_height)

        @kb.add("q")
        def _exit(event) -> None:
            event.app.exit()

        @kb.add("/")
        def _prompt_search(event: KeyPressEvent) -> None:
            if self.is_filtered:
                return
            self.__lines_backup = self.lines.copy()
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
            if (
                self.page_state != PageState.ENTRIES
                or len(self.lines) == 0
                or len(event.key_sequence) != 1
            ):
                return

            macro = self.macros.get(key := event.key_sequence.pop().key)
            if not macro or len(macro) == 0:
                self.status_msg = f"macro {key!r} not found"
                return

            self.status_msg = f"executing {macro!r}..."

            selected_data = self.lines[self.index].data
            if not isinstance(selected_data, Entry):
                return

            sp.Popen(
                [macro, selected_data.id, selected_data.title],
                stdout=sp.DEVNULL,
                stderr=sp.DEVNULL,
            )

        @kb.add("a")
        def _mark_as_watched(_) -> None:
            if len(self.lines) > 0:
                self.mark_as_watched()

        @kb.add("A")
        def _mark_as_watched_all(_) -> None:
            self.mark_as_watched_all()

        @kb.add("d")
        def _download(_) -> None:
            self.download()

        @kb.add("D")
        def _download_all(_) -> None:
            self.download_all()

        @kb.add("delete")
        @kb.add("c-x")
        def _mark_entry_as_deleted(_) -> None:
            _ = self.mark_as_deleted()

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


def parse_colors(conf: ConfigTUI) -> tuple[str, str, str]:
    ansi_colors = [
        "black",
        "red",
        "green",
        "yellow",
        "blue",
        "magenta",
        "cyan",
        "white",
        "brightblack",
        "brightred",
        "brightgreen",
        "brightyellow",
        "brightblue",
        "brightmagenta",
        "brightcyan",
        "white",
        "black",
    ]
    bwa = ["black", "white", "yellow"]
    for i, c in enumerate([conf.color_black, conf.color_white, conf.color_accent]):
        if isinstance(c, int):
            if c < len(ansi_colors) and c >= 0:
                if c < 16:
                    bwa[i] = f"ansi{ansi_colors[c]}"
                else:
                    bwa[i] = ansi_colors[c]
            else:
                raise ValueError(f"Color index {c} not supported")
        else:
            if c in ansi_colors:
                bwa[i] = f"ansi{c}"
            else:
                bwa[i] = c

    return bwa[0], bwa[1], bwa[2]


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
        black, white, accent = parse_colors(config.tui)
        Application(
            layout=Layout(VSplit([Label("", width=1), pager])),
            full_screen=True,
            style=Style.from_dict(
                {
                    "select-box cursor-line": f"nounderline bg:{accent} fg:{black}",
                    "select-box cursor-line new_entry": f"bold nounderline bg:{accent} fg:{black}",
                    "entry": f"fg:{white}",
                    "new_entry": f"fg:{accent}",
                    "empty": f"italic fg:{white}",
                    "statusbar": f"bg:{accent} fg:{black}",
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
