from enum import Enum, auto
import subprocess as sp
import sys

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition, has_focus
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
    Window,
)
from prompt_toolkit.layout.processors import BeforeInput, Processor
from prompt_toolkit.styles import Style

from pytfeeder import Config, Feeder, Storage, __version__
from pytfeeder.logger import init_logger
from pytfeeder.models import Channel, Entry, Tag
from pytfeeder.tui import args as tui_args, ConfigTUI
from pytfeeder.tui.props import TuiProps, PageState, Line


class PromptContainer(ConditionalContainer):
    def __init__(
        self,
        app: "App",
        buffer: Buffer,
        prompt_text: str = "/",
        ip: Processor | None = None,
    ):
        kb = KeyBindings()

        @kb.add("escape")
        @kb.add("c-c")
        def _cancel(_) -> None:
            buffer.text = ""
            app._focus_main_window()

        super(PromptContainer, self).__init__(
            Window(
                BufferControl(
                    buffer=buffer,
                    input_processors=[ip or BeforeInput(prompt_text)],
                    key_bindings=kb,
                ),
                height=1,
            ),
            filter=has_focus(buffer),
        )


class ConfirmType(Enum):
    NONE = auto()
    DELETE = auto()
    DOWNLOAD = auto()


class App(TuiProps):
    def __init__(self, feeder: Feeder) -> None:
        super().__init__(feeder)

        self.classnames = {0: "entry", 1: "new-entry"}
        self.filter_text = ""
        self.help_index = 0
        self.is_help_opened = False
        self.macros = {
            "f1": self.c.macro1,
            "f2": self.c.macro2,
            "f3": self.c.macro3,
            "f4": self.c.macro4,
        }
        self.status_title = ""

        self.statusbar_window = Window(
            always_hide_cursor=True,
            height=Dimension.exact(self.statusbar_height),
            content=FormattedTextControl(
                text=self._get_statusbar_text,
                focusable=False,
            ),
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
            self._focus_main_window()
            if buf.text == "":
                return False
            condition = lambda v: buf.text.lower() in v.data.title.lower()
            self.lines = list(filter(condition, self.lines))
            self.is_filtered = True
            self.index = 0
            buf.text = ""
            return True

        self.filter_buffer = Buffer(multiline=False, accept_handler=filter_handler)

        def jump_handler(buf: Buffer) -> bool:
            self._focus_main_window()
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

        self.confirm_type_prompt = ConfirmType.NONE

        self.confirm_buffer = Buffer(
            multiline=False,
            on_text_changed=self.confirm_handler,
        )

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

        self.layout = HSplit(
            [
                self.main_window,
                self.help_window,
                self.statusbar_window,
                PromptContainer(self, self.filter_buffer),
                PromptContainer(self, self.jump_buffer, prompt_text=":"),
                PromptContainer(
                    self,
                    self.confirm_buffer,
                    ip=BeforeInput(self.__confirm_prompt_text),
                ),
            ]
        )

        _kb = KeyBindings()

        @_kb.add("c-c")
        def _(event):
            event.app.exit()

        self._app = Application(
            layout=Layout(self.layout),
            full_screen=True,
            style=self.style,
            key_bindings=_kb,
        )

    @property
    def style(self) -> Style:
        black, white, accent = parse_colors(self.c)
        return Style.from_dict(
            {
                "select-box cursor-line": f"nounderline bg:{accent} fg:{black}",
                "select-box cursor-line new-entry": f"bold nounderline bg:{accent} fg:{black}",
                "entry": f"fg:{white}",
                "new-entry": f"fg:{accent}",
                "empty": f"italic fg:{white}",
                "new-empty": f"italic fg:{accent}",
                "statusbar": f"bg:{accent} fg:{black}",
                "statusbar.text": "",
            },
        )

    def start(self) -> None:
        self._app.run(set_exception_handler=False)

    def __confirm_prompt_text(self) -> str:
        if self.confirm_type_prompt == ConfirmType.DELETE:
            return f"Delete all {len(self.lines)} entries (y/N)?"
        elif self.confirm_type_prompt == ConfirmType.DOWNLOAD:
            return f"Download all {len([0 for l in self.lines if isinstance(l.data, Entry) and not l.data.is_viewed])} entries (y/N)?"
        return ""

    def confirm_handler(self, buf: Buffer) -> None:
        self._focus_main_window()

        t = buf.text.lower()
        buf.text = ""
        if t != "y":
            return

        if self.confirm_type_prompt == ConfirmType.DELETE:
            if self.mark_all_as_deleted():
                self.move_back_to_channels()
        elif self.confirm_type_prompt == ConfirmType.DOWNLOAD:
            self.download_all()
        self.confirm_type_prompt = ConfirmType.NONE

    def _focus_main_window(self) -> None:
        app = get_app()
        app.layout.focus(self.main_window)
        app.vi_state.input_mode = InputMode.NAVIGATION

    def format_channel(
        self, i: int, channel: Channel | Tag
    ) -> list[OneStyleAndTextTuple]:
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
        classname = self.classnames[not entry.is_viewed]
        if self.page_state == PageState.RESTORING_ENTRIES and entry.is_deleted:
            classname = ["empty", "new-empty"][not entry.is_viewed]
        return [(f"class:{classname}", line)]

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
            elif isinstance(line.data, Channel) or isinstance(line.data, Tag):
                result.append(self.format_channel(i, line.data))
            result.append("\n")

        return merge_formatted_text(result)

    def _get_formatted_help_text(self) -> AnyFormattedText:
        result: list[AnyFormattedText] = []
        for i, line in enumerate(self.help_lines):
            if i == self.help_index:
                result.append([("[SetCursorPosition]", "")])
            result.append([(f"class:{self.classnames[0]}", line)])
            if i < len(self.help_lines) - 1:
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
        self.status_title = ""
        self._reset_filter()

    @property
    def _help_keybindings(self) -> KeyBindings:
        kb = KeyBindings()

        @kb.add("g", "g")
        def _go_top(_):
            self.help_index = 0

        @kb.add("G")
        def _go_bottom(_):
            self.help_index = max(0, len(self.help_lines) - 1)

        @kb.add("k")
        @kb.add("up")
        def _go_up(e: KeyPressEvent) -> None:
            w = e.app.layout.current_window
            if not w or not w.render_info:
                return

            self.help_index = max(0, w.vertical_scroll - 1)

        @kb.add("j")
        @kb.add("down")
        def _go_down(e: KeyPressEvent) -> None:
            w = e.app.layout.current_window
            if not w or not w.render_info:
                return

            h = w.render_info.window_height
            w.vertical_scroll += 1
            if self.help_index < h:
                self.help_index = min(h, len(self.help_lines) - 1)
            else:
                self.help_index = min(self.help_index + 1, len(self.help_lines) - 1)

        @kb.add("b")
        @kb.add("h")
        @kb.add("left")
        @kb.add("q")
        @kb.add("?")
        def _go_back(event: KeyPressEvent) -> None:
            self.is_help_opened = False
            self.help_window.height = 0
            self.main_window.height = self.layout.height
            event.app.layout.reset()
            event.app.layout.focus(self.main_window)
            self.status_title = ""

        return kb

    def move_back_to_channels(self) -> None:
        self.page_state = PageState.CHANNELS
        self.lines = list(map(Line, self.channels))
        self.index = max(self.parent_index, 0)
        self.parent_index = -1
        self.parent_index_restore = -1
        self.parent_index_tags = -1
        self.status_title = ""

    @property
    def _main_keybindings(self) -> KeyBindings:
        kb = KeyBindings()

        @Condition
        def have_lines() -> bool:
            return len(self.lines) > 0

        @kb.add("k", filter=have_lines)
        @kb.add("up", filter=have_lines)
        def _up(_) -> None:
            self.index = (self.index - 1) % len(self.lines)

        @kb.add("j", filter=have_lines)
        @kb.add("down", filter=have_lines)
        def _down(_) -> None:
            self.index = (self.index + 1) % len(self.lines)

        @kb.add("b", filter=have_lines)
        @kb.add("pageup", filter=have_lines)
        def _backward(_) -> None:
            if not self.main_window.render_info:
                return
            h = self.main_window.render_info.window_height
            if self.index == 0:
                self.index = len(self.lines) - 1
            elif (self.index - h) < 0:
                self.index = 0
            else:
                self.index = (self.index - h) % len(self.lines)

        @kb.add("f", filter=have_lines)
        @kb.add("pagedown", filter=have_lines)
        def _forward(_) -> None:
            if not self.main_window.render_info:
                return
            h = self.main_window.render_info.window_height
            if self.index == len(self.lines) - 1:
                self.index = 0
            elif (self.index + h) >= len(self.lines):
                self.index = len(self.lines) - 1
            else:
                self.index = (self.index + h) % len(self.lines)

        @kb.add("l", filter=have_lines)
        @kb.add("o", filter=have_lines)
        @kb.add("enter", filter=have_lines)
        @kb.add("right", filter=have_lines)
        @kb.add("space", filter=have_lines)
        def _enter_line(e: KeyPressEvent) -> None:
            if self.index not in range(len(self.lines)):
                raise Exception(f"{self.index=} out of range 0-{len(self.lines)}")

            selected_data = self.lines[self.index].data
            if self.page_state == PageState.ENTRIES:
                if not isinstance(selected_data, Entry):
                    raise Exception(f"Unexpected entry type {type(selected_data) = !r}")

                self.play(selected_data)
                if not selected_data.is_viewed:
                    self.mark_as_watched()
                return
            elif self.page_state == PageState.RESTORING_ENTRIES:
                if not isinstance(selected_data, Entry):
                    raise Exception(f"Unexpected entry type {type(selected_data) = !r}")
                self.toggle_is_deleted(selected_data)
                return
            elif self.page_state == PageState.TAGS:
                if not isinstance(selected_data, Tag):
                    raise Exception(f"Unexpected tag type {type(selected_data) = !r}")
                if self.is_filtered:
                    self.reset_filter()
                    self.index = self.find_tag_index(selected_data.title)
                self.select_tag(selected_data)
                self.status_title = selected_data.title
                return

            if not isinstance(selected_data, Channel):
                raise Exception(f"Unexpected channel type {type(selected_data) = !r}")

            if self.page_state == PageState.RESTORING:
                if {"o", "l", "right"} & {kp.key for kp in e.key_sequence}:
                    reset_filter = self.is_filtered
                    if self.enter_restore_entries():
                        if reset_filter:
                            self.filter_text = ""
                    return
                if not self.restore_channel(selected_data):
                    return
                self.page_state = PageState.CHANNELS
                if self.is_filtered:
                    self.reset_filter()
                self.enter_restore()
                return

            if selected_data.entries_count == 0:
                return

            if not self.is_filtered and self.page_state != PageState.TAGS_CHANNELS:
                self.parent_index = self.index
            else:
                self.parent_index = self.find_channel_index_by_id(
                    selected_data.channel_id
                )
                if self.is_filtered:
                    self.reset_filter()

            self.lines = self.get_lines_by_id(selected_data.channel_id)
            self.page_state = PageState.ENTRIES
            self.index = 0
            self.status_title = selected_data.title

        @kb.add("h")
        @kb.add("left")
        @kb.add("backspace")
        def _back(event) -> None:
            if self.is_help_opened:
                self.is_help_opened = False
                return

            if self.is_channels_outdated:
                self.update_channels()

            if self.is_filtered:
                self.reset_filter()
                if self.page_state == PageState.RESTORING:
                    self.page_state = PageState.CHANNELS
                    _ = self.enter_restore()
                elif self.page_state == PageState.RESTORING_ENTRIES:
                    if len(self.lines):
                        channel_id = self.lines[self.index].data.channel_id  # type: ignore
                    elif self._restore_entries_channel_id:
                        channel_id = self._restore_entries_channel_id
                    else:
                        raise Exception("Unknown parent channel")
                    self.enter_restore_entries(channel_id)
                elif (
                    self.page_state == PageState.TAGS_CHANNELS
                    and self.parent_index_tags > -1
                ):
                    self.index = self.parent_index_tags
                    tag = self.tag_by_index(self.parent_index_tags)
                    self.select_tag(tag)
                    self.status_title = tag.title
            elif self.page_state == PageState.CHANNELS:
                event.app.exit()
            elif self.page_state == PageState.TAGS_CHANNELS and self.show_tags():
                self.status_title = "TAGS"
            elif self.page_state == PageState.RESTORING_ENTRIES:
                self.enter_restore(self.parent_index_restore, is_move_back=True)
            elif self.parent_index_tags > -1:
                if self.is_filtered:
                    self.filter_text = ""
                self.move_back_to_tag()
                self.status_title = self.tag_by_index(self.parent_index_tags).title
            else:
                self.move_back_to_channels()

        @kb.add("p", filter=have_lines)
        def _prev_unwatched(_) -> None:
            self.move_prev_unwatched()

        @kb.add("n", filter=have_lines)
        def _next_unwatched(_) -> None:
            self.move_next_unwatched()

        @kb.add("g", "g")
        @kb.add("home")
        def _top(_) -> None:
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

        @kb.add("F")
        def _follow(_) -> None:
            if (
                self.page_state != PageState.ENTRIES
                or not self._is_feed_opened
                or self.parent_index != 0
            ):
                return

            selected_data = self.lines[self.index].data
            if not isinstance(selected_data, Entry):
                return

            self.parent_index = self.find_channel_index_by_id(selected_data.channel_id)
            self.is_filtered = False
            self.lines = self.get_lines_by_id(selected_data.channel_id)
            self.index = 0
            self.status_title = self.channels[self.parent_index].title

        @kb.add("s")
        def _toggle_status_visability(_) -> None:
            self.c.hide_statusbar = not self.c.hide_statusbar
            self.statusbar_window.height = Dimension.exact(self.statusbar_height)

        @kb.add("t")
        def _toggle_empty_channels_visability(_) -> None:
            self.toggle_empty_channels_visability()

        @kb.add("q")
        def _exit(event) -> None:
            if (
                self.page_state == PageState.TAGS
                or self.page_state == PageState.RESTORING
            ):
                if self.is_filtered:
                    self.reset_filter()
                self.move_back_to_channels()
            elif self.page_state == PageState.TAGS_CHANNELS:
                if not self.show_tags():
                    self.move_back_to_channels()
            elif self.page_state == PageState.RESTORING_ENTRIES:
                if self.is_filtered:
                    self.reset_filter()
                self.index = 0
                self.enter_restore()
            elif self.page_state == PageState.ENTRIES and self.parent_index_tags > -1:
                if self.is_filtered:
                    self.filter_text = ""
                self.move_back_to_tag()
                self.status_title = self.tag_by_index(self.parent_index_tags).title
            else:
                event.app.exit()

        @kb.add("/")
        def _prompt_search(event: KeyPressEvent) -> None:
            if self.is_filtered:
                return
            event.app.layout.focus(self.filter_buffer)
            event.app.vi_state.input_mode = InputMode.INSERT

        for n in "123456789":

            @kb.add(n)
            def _prompt_jump(event: KeyPressEvent) -> None:
                event.app.layout.focus(self.jump_buffer)
                event.app.vi_state.input_mode = InputMode.INSERT
                self.jump_buffer.text = str(event.key_sequence.pop().key)
                self.jump_buffer.cursor_position = 1

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

        def setup_confirm_prompt(event: KeyPressEvent) -> None:
            event.app.layout.focus(self.confirm_buffer)
            event.app.vi_state.input_mode = InputMode.INSERT

        @kb.add("D")
        def _download_all(event: KeyPressEvent) -> None:
            if self.page_state != PageState.ENTRIES or len(self.lines) == 0:
                return
            if not any(not l.data.is_viewed for l in self.lines):  # type: ignore
                return
            self.confirm_type_prompt = ConfirmType.DOWNLOAD
            setup_confirm_prompt(event)

        @kb.add("delete")
        @kb.add("c-x")
        def _mark_entry_as_deleted(_) -> None:
            if self.mark_as_deleted() and len(self.lines) == 0:
                self.update_channels()
                self.move_back_to_channels()

        @kb.add("c-d")
        def _mark_all_as_deleted(event: KeyPressEvent) -> None:
            if (
                self.page_state != PageState.ENTRIES
                or len(self.lines) == 0
                or self.is_filtered
                or self._is_feed_opened
            ):
                return
            self.confirm_type_prompt = ConfirmType.DELETE
            setup_confirm_prompt(event)

        @kb.add("c-r")
        def _enter_restore(_) -> None:
            if self.enter_restore(0):
                self.status_title = "RESTORING"

        @kb.add("c-o")
        def _open_channel_in_browser(_) -> None:
            self.open_channel_in_browser()

        @kb.add("tab")
        def _show_tags(_) -> None:
            if self.is_filtered or self.page_state == PageState.RESTORING:
                return
            if self.page_state == PageState.TAGS:
                self.move_back_to_channels()
            elif self.show_tags():
                self.status_title = "TAGS"

        @kb.add("u")
        def _toggle_unwatched_first(_) -> None:
            self.toggle_unwathced_first()

        @kb.add("?")
        def _open_help(event: KeyPressEvent) -> None:
            if not self.is_help_opened:
                self.is_help_opened = True
                event.app.layout.reset()
                self.main_window.height = 0
                self.help_window.reset()
                self.help_window.height = self.layout.height
                event.app.layout.focus(self.help_window)
            else:
                self.is_help_opened = False
                event.app.layout.focus(self.main_window)

        @kb.add("r")
        async def _reload(event: KeyPressEvent) -> None:
            if self.page_state == PageState.RESTORING:
                return
            self.status_msg = "updating..."
            event.app.invalidate()
            await self.sync_and_reload()

        @kb.add("c")
        def _clear(event: KeyPressEvent) -> None:
            event.app.renderer.clear()

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
    config = Config(config_file=args.config, channels_filepath=args.channels_file)
    config.tui.update(vars(args))

    if not config.storage_path.parent.exists():
        config.storage_path.parent.mkdir(parents=True)

    init_logger(config.logger)

    feeder = Feeder(config, Storage(config.storage_path))
    if len(feeder.channels) == 0:
        print(f"No channels configured in {feeder.config.channels_filepath}")
        sys.exit(0)

    try:
        App(feeder).start()
    except Exception as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
