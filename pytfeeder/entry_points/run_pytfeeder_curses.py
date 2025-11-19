import asyncio
import curses
from enum import Enum, IntEnum, auto
import re
from typing import Literal
import sys

from pytfeeder import Config, Feeder, Storage, __version__
from pytfeeder.logger import init_logger, LogLevel
from pytfeeder.models import Channel, Entry, Tag
from pytfeeder.tui import args as tui_args, ConfigTUI
from pytfeeder.tui.props import TuiProps, PageState, Line


class Key(IntEnum):
    CTRL_D = 4
    CTRL_F = 6
    CTRL_H = 8
    TAB = 9
    RETURN = ord("\n")
    CTRL_O = 15
    CTRL_R = 18
    CTRL_X = 24
    ESC = 27
    SPACE = 32
    SLASH = ord("/")
    N1 = ord("1")
    N2 = ord("2")
    N3 = ord("3")
    N4 = ord("4")
    N5 = ord("5")
    N6 = ord("6")
    N7 = ord("7")
    N8 = ord("8")
    N9 = ord("9")
    QUESTION_MARK = ord("?")
    A = ord("A")
    D = ord("D")
    F = ord("F")
    G = ord("G")
    J = ord("J")
    K = ord("K")
    O = ord("O")
    S = ord("S")
    a = ord("a")
    b = ord("b")
    c = ord("c")
    d = ord("d")
    f = ord("f")
    g = ord("g")
    h = ord("h")
    j = ord("j")
    k = ord("k")
    l = ord("l")
    n = ord("n")
    o = ord("o")
    p = ord("p")
    q = ord("q")
    r = ord("r")
    s = ord("s")
    t = ord("t")
    u = ord("u")
    F1 = 265
    F2 = 266
    F3 = 267
    F4 = 268


class Gravity(IntEnum):
    DOWN = 1
    UP = -1


class ColorIndex(IntEnum):
    BLACK = 17
    WHITE = 18
    ACCENT = 19


class ColorPair(IntEnum):
    NONE = 1
    ACTIVE = 2
    NEW = 3


def parse_colors(conf: ConfigTUI) -> tuple[int, int, int]:
    bwa = [curses.COLOR_BLACK, curses.COLOR_WHITE, curses.COLOR_YELLOW]
    reserved = [ColorIndex.BLACK, ColorIndex.WHITE, ColorIndex.ACCENT]
    for i, c in enumerate([conf.color_black, conf.color_white, conf.color_accent]):
        if isinstance(c, str):
            new_c = getattr(curses, f"COLOR_{c.upper()}", None)
            if isinstance(new_c, int):
                c = new_c
            elif re.match("^#[a-f0-9]{3,6}$", c):
                curses.init_color(reserved[i], *hex_to_rgb(c))
                c = reserved[i]
            else:
                raise ValueError(f"Invalid color value {c!r}")
        else:
            if c in reserved:
                raise ValueError(f"Color index {c} are reserved")
        bwa[i] = c
    return bwa[0], bwa[1], bwa[2]


def hex_to_rgb(c: str) -> tuple[int, int, int]:
    if len(c) == 7:
        r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
    elif len(c) == 4:
        r, g, b = int(c[1] * 2, 16), int(c[2] * 2, 16), int(c[3] * 2, 16)
    else:
        raise ValueError(f"Unexpected hex color value {len(c) = } ({c = })")
    return (r * 1000) // 255, (g * 1000) // 255, (b * 1000) // 255


class CLIType(Enum):
    FILTER = auto()
    JUMP = auto()
    CONFIRM = auto()


class App(TuiProps):
    def __init__(self, feeder: Feeder) -> None:
        super().__init__(feeder)

        self._g_pressed = False
        self.gravity = Gravity.DOWN
        self.macros = {
            Key.F1: self.c.macro1,
            Key.F2: self.c.macro2,
            Key.F3: self.c.macro3,
            Key.F4: self.c.macro4,
        }
        self.scroll_top = 0

    def start(self) -> None:
        curses.wrapper(self._start)

    def _start(self, screen: curses.window) -> None:
        self.config_curses()
        try:
            self.run_loop(screen)
        except KeyboardInterrupt:
            pass

    def config_curses(self) -> None:
        curses.curs_set(0)
        if curses.has_colors():
            curses.use_default_colors()
        if not curses.has_extended_color_support() or not curses.can_change_color():
            return

        black, white, accent = parse_colors(self.c)
        curses.init_pair(ColorPair.NONE, white, -1)
        curses.init_pair(ColorPair.ACTIVE, black, accent)
        curses.init_pair(ColorPair.NEW, accent, -1)

    def run_loop(self, screen: curses.window) -> None:
        while True:
            self.draw(screen)
            ch = screen.getch()
            match ch:
                case Key.j | curses.KEY_DOWN:
                    if len(self.lines) > 0:
                        self.move_down()
                case Key.k | curses.KEY_UP:
                    if len(self.lines) > 0:
                        self.move_up()
                case Key.b | curses.KEY_PPAGE:
                    if len(self.lines) > 0:
                        max_y, _ = screen.getmaxyx()
                        self.move_backward(max_y - self.statusbar_height)
                case Key.f | curses.KEY_NPAGE:
                    if len(self.lines) > 0:
                        max_y, _ = screen.getmaxyx()
                        self.move_forward(max_y - self.statusbar_height)
                case Key.l | Key.o | curses.KEY_RIGHT | Key.RETURN | Key.SPACE:
                    if len(self.lines) > 0:
                        screen.clear()
                        self.move_right(ch)
                case Key.h | curses.KEY_LEFT | curses.KEY_BACKSPACE:
                    self.move_left(screen)
                    screen.refresh()
                case Key.p:
                    before = self.index
                    self.move_prev_unwatched()
                    if before != self.index:
                        self.gravity = Gravity.DOWN
                        if before - self.index == 1:
                            self.gravity = Gravity.UP
                case Key.n:
                    before = self.index
                    self.move_next_unwatched()
                    if before != self.index:
                        self.gravity = Gravity.DOWN
                case Key.r:
                    if self.page_state == PageState.RESTORING:
                        continue
                    self.status_msg = "updating..."
                    self.draw(screen)
                    asyncio.run(self.sync_and_reload())
                case curses.KEY_HOME:
                    self.move_top()
                case Key.g:
                    if self._g_pressed:
                        self.move_top()
                    self._g_pressed = not self._g_pressed
                case Key.G | curses.KEY_END:
                    self.move_bottom()
                case Key.SLASH:
                    if not self.is_filtered:
                        self.handle_input(screen)
                case Key.F1 | Key.F2 | Key.F3 | Key.F4:
                    self.handle_macro(ch)
                case (
                    Key.N1
                    | Key.N2
                    | Key.N3
                    | Key.N4
                    | Key.N5
                    | Key.N6
                    | Key.N7
                    | Key.N8
                    | Key.N9
                ):
                    self.handle_input(screen, cli_type=CLIType.JUMP, n=ch)
                case Key.a:
                    self.mark_as_watched()
                case Key.A:
                    self.mark_as_watched_all()
                case Key.J:
                    if self.handle_move(Gravity.DOWN):
                        self.scroll_top = 0
                        screen.clear()
                case Key.K:
                    if self.handle_move(Gravity.UP):
                        self.scroll_top = 0
                        screen.clear()
                case Key.F:
                    if self.handle_follow():
                        screen.clear()
                case Key.QUESTION_MARK:
                    self.open_help(screen)
                case Key.d:
                    self.download()
                case Key.D:
                    self.download_all(
                        lambda n: bool(
                            self.handle_input(
                                screen,
                                CLIType.CONFIRM,
                                prefix=f"Download all {n} entries (y/N)?",
                            )
                        )
                    )
                case Key.CTRL_X | curses.KEY_DC:
                    if self.mark_as_deleted():
                        screen.clear()
                        if len(self.lines) == 0:
                            if self.parent_index_tags > -1:
                                self.move_back_to_tag()
                            else:
                                self.move_back_to_channels()
                case Key.CTRL_D:
                    if (
                        self.page_state != PageState.ENTRIES
                        or len(self.lines) == 0
                        or self.is_filtered
                        or self._is_feed_opened
                        or not self.handle_input(
                            screen,
                            CLIType.CONFIRM,
                            prefix=f"Delete all {len(self.lines)} entries (y/N)?",
                        )
                    ):
                        continue
                    if self.mark_all_as_deleted():
                        screen.clear()
                        if self.parent_index_tags > -1:
                            self.move_back_to_tag()
                        else:
                            self.move_back_to_channels()
                case Key.CTRL_F:
                    if self.c.hide_feed or self._is_feed_opened:
                        continue
                    self.page_state = PageState.CHANNELS
                    self.index = 0
                    self.reset_filter()
                    self.move_right(Key.l)
                case Key.CTRL_H:
                    if self.page_state == PageState.CHANNELS:
                        continue
                    self.scroll_top = 0
                    screen.clear()
                    self.move_home()

                case Key.CTRL_R:
                    if self.enter_restore(0):
                        screen.clear()
                case Key.CTRL_O:
                    self.open_in_browser()
                case Key.O:
                    self.open_in_browser(always_channel=True)
                case Key.TAB:
                    if self.is_filtered or self.page_state == PageState.RESTORING:
                        continue
                    if self.page_state == PageState.TAGS:
                        self.move_back_to_channels()
                    elif self.show_tags():
                        screen.clear()

                case Key.s:
                    self.toggle_alphabetic_sort()

                case Key.S:
                    self.c.hide_statusbar = not self.c.hide_statusbar
                    max_y, _ = screen.getmaxyx()
                    self.gravity = Gravity.UP
                    self.update_scroll_top(max_rows=max_y - self.statusbar_height)
                    screen.clear()

                case Key.t:
                    before = len(self.lines)
                    self.toggle_empty_channels_visability()
                    if len(self.lines) < before:
                        self.scroll_top = 0
                        screen.clear()
                case Key.u:
                    if self.page_state == PageState.RESTORING:
                        continue
                    self.toggle_unwathced_first()
                    if self.page_state == PageState.ENTRIES:
                        self.scroll_top = 0
                case Key.c:
                    screen.clear()
                case Key.q:
                    screen.clear()
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
                            self.gravity = Gravity.DOWN
                        if (
                            self._is_in_restore_from_channel
                            and self._restore_entries_channel_id
                        ):
                            self.page_state = PageState.ENTRIES
                            self.lines = self.get_lines_by_id(
                                self._restore_entries_channel_id
                            )
                        else:
                            self.enter_restore(
                                self.parent_index_restore, is_move_back=True
                            )
                        self.scroll_top = 0
                        self.index = 0
                    elif (
                        self.page_state == PageState.ENTRIES
                        and self.parent_index_tags > -1
                    ):
                        self.move_back_to_tag()
                    else:
                        sys.exit(0)

    def draw(self, screen: curses.window) -> None:
        x = 0  # y = 0
        max_y, max_x = screen.getmaxyx()
        max_rows = max_y - self.statusbar_height
        self.update_scroll_top(max_rows)
        index_len = len(str(len(self.lines)))
        for i, line in enumerate(
            self.lines[self.scroll_top : self.scroll_top + max_rows]
        ):
            is_active = i + self.scroll_top == self.index
            attr = None
            color = ColorPair.NONE
            text = "-"
            index = f"{i + 1 + self.scroll_top:{index_len}d}"
            highlight = False

            if isinstance(line.data, Entry):
                if (
                    self.page_state == PageState.RESTORING_ENTRIES
                    and line.data.is_deleted
                ):
                    attr = curses.A_DIM | curses.A_ITALIC
                highlight = not line.data.is_viewed
                published = line.data.published.strftime(self.c.datetime_fmt)
                text = self.current_entry_format.format(
                    index=index,
                    new_mark=self.new_marks[highlight],
                    published=published,
                    title=line.data.title,
                    channel_title=self.channel_title(line.data.channel_id),
                )

            elif isinstance(line.data, Channel) or isinstance(line.data, Tag):
                highlight = line.data.have_updates
                if line.data.entries_count == 0:
                    attr = curses.A_DIM | curses.A_ITALIC
                text = self.c.channels_fmt.format(
                    index=index,
                    new_mark=self.new_marks[highlight],
                    title=line.data.title,
                    unwatched=line.data.unwatched_count,
                    total=line.data.entries_count,
                    unwatched_total=self.format_unwatched_total_key(line.data),
                )

            if highlight and is_active:
                color = ColorPair.ACTIVE
                attr = curses.A_BOLD
            elif is_active:
                color = ColorPair.ACTIVE
            elif highlight:
                color = ColorPair.NEW

            if attr is None:
                attr = curses.color_pair(color)
            else:
                attr = curses.color_pair(color) | attr

            text = f"{text:<{max_x}}"
            try:
                screen.addnstr(i, x, text, max_x, attr)
            except:
                pass

        if self.statusbar_height:
            try:
                screen.addnstr(
                    max_y - 1,
                    x,
                    f"{self.status:<{max_x}}",
                    max_x,
                    curses.color_pair(ColorPair.ACTIVE),
                )
            except:
                pass
        screen.refresh()

    def update_scroll_top(self, max_rows: int) -> None:
        match self.gravity:
            case Gravity.DOWN:
                if (self.index + 1) - self.scroll_top > max_rows:
                    self.scroll_top = (self.index + 1) - max_rows
                if self.index + 1 < self.scroll_top:
                    self.scroll_top = self.index
                if self.index == 0:
                    self.scroll_top = self.index
            case Gravity.UP:
                if self.index + 1 == self.scroll_top:
                    self.scroll_top = max(self.scroll_top - 1, 0)
                if self.index + 1 == len(self.lines):
                    self.scroll_top = max((self.index + 1) - max_rows, 0)

    def handle_macro(self, key: Literal[Key.F1, Key.F2, Key.F3, Key.F4]) -> None:
        if self.page_state != PageState.ENTRIES:
            return
        if len(self.lines) == 0:
            return
        macro = self.macros.get(key)
        if not macro or len(macro) == 0:
            return

        selected_data = self.lines[self.index].data
        if not isinstance(selected_data, Entry):
            return

        cmd = macro.format(id=selected_data.id, title=selected_data.title)
        self.status_msg = f"executing {cmd!r}..."
        self.cmd.execute_macro(cmd)

    def open_help(self, screen: curses.window) -> None:
        screen.clear()
        max_y, max_x = screen.getmaxyx()
        pad_pos = 0
        pad = curses.newpad(len(self.help_lines) + 1, max_x)

        for i, line in enumerate(self.help_lines):
            text = f"{line}"
            pad.addnstr(i, 0, text, min(len(text), max_x))

        pad.addnstr(len(self.help_lines), 0, "~", 1)

        pad.refresh(pad_pos, 0, 0, 0, max_y - 2, max_x - 1)
        screen.refresh()

        while True:
            max_y, max_x = screen.getmaxyx()
            pad.refresh(pad_pos, 0, 0, 0, max_y - 2, max_x - 1)
            try:
                screen.addnstr(
                    max_y - 1,
                    0,
                    f"{self.help_status:<{max_x}}",
                    max_x,
                    curses.color_pair(ColorPair.ACTIVE),
                )
            except:
                pass

            match screen.getch():
                case Key.h | curses.KEY_LEFT | Key.q:
                    screen.clear()
                    self.gravity = Gravity.DOWN
                    break
                case Key.j | curses.KEY_DOWN:
                    pad_pos = min(pad_pos + 1, pad.getyx()[0] - (max_y - 1))
                case Key.k | curses.KEY_UP:
                    pad_pos = max(0, pad_pos - 1)
                case Key.g | curses.KEY_HOME:
                    pad_pos = 0
                case Key.G | curses.KEY_END:
                    pad_pos = (len(self.help_lines) + 1) - max_y
                case curses.KEY_RESIZE:
                    screen.refresh()

    def move_up(self) -> None:
        self.gravity = Gravity.UP
        self.index = (self.index - 1) % len(self.lines)

    def move_top(self) -> None:
        self.gravity = Gravity.DOWN
        self.index = 0

    def move_down(self) -> None:
        self.gravity = Gravity.DOWN
        self.index = (self.index + 1) % len(self.lines)

    def move_backward(self, h: int) -> None:
        if h == 0:
            return
        if self.index == 0:
            self.index = len(self.lines) - 1
        elif (self.index - h) < 0:
            self.index = 0
        else:
            self.index = (self.index - h) % len(self.lines)
            self.scroll_top = self.index
        self.gravity = Gravity.DOWN

    def move_forward(self, h: int) -> None:
        if h == 0:
            return
        if self.index == len(self.lines) - 1:
            self.index = 0
        elif (self.index + h) >= len(self.lines):
            self.index = len(self.lines) - 1
        else:
            self.index = (self.index + h) % len(self.lines)
        self.gravity = Gravity.DOWN

    def move_bottom(self) -> None:
        self.gravity = Gravity.DOWN
        self.index = len(self.lines) - 1

    def handle_follow(self) -> bool:
        if (
            self.page_state != PageState.ENTRIES
            or not self._is_feed_opened
            or self.parent_index != 0
        ):
            return False

        selected_data = self.lines[self.index].data
        if not isinstance(selected_data, Entry):
            return False
        self.parent_index = self.find_channel_index_by_id(selected_data.channel_id)
        self.is_filtered = False
        self.lines = self.get_lines_by_id(selected_data.channel_id)
        self.index = 0
        self.scroll_top = 0
        return True

    def move_left(self, screen: curses.window) -> None:
        if len(self.lines) > 0:
            screen.clear()
        if self.is_filtered:
            self.reset_filter()
            if self.page_state == PageState.RESTORING:
                self.page_state = PageState.CHANNELS
                if self.enter_restore():
                    screen.clear()
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
                self.select_tag(self.tag_by_index(self.parent_index_tags))

            self.draw(screen)
        elif self.page_state == PageState.CHANNELS:
            sys.exit(0)
        elif (
            self.page_state == PageState.ENTRIES
            or self.page_state == PageState.RESTORING
            or self.page_state == PageState.TAGS
        ):
            if self.page_state == PageState.ENTRIES and self.parent_index_tags > -1:
                self.move_back_to_tag()
            else:
                self.move_back_to_channels()
        elif self.page_state == PageState.TAGS_CHANNELS and self.show_tags():
            screen.clear()
        elif self.page_state == PageState.RESTORING_ENTRIES:
            self.gravity = Gravity.DOWN
            if self._is_in_restore_from_channel and self._restore_entries_channel_id:
                self.page_state = PageState.ENTRIES
                self.lines = self.get_lines_by_id(self._restore_entries_channel_id)
            else:
                self.enter_restore(self.parent_index_restore, is_move_back=True)

    def move_right(self, ch: int) -> None:
        selected_data = self.lines[self.index].data

        if self.page_state == PageState.CHANNELS and isinstance(selected_data, Channel):
            if selected_data.entries_count == 0:
                return
            self.page_state = PageState.ENTRIES
            self.lines = self.get_lines_by_id(selected_data.channel_id)

            if self.is_filtered:
                self.parent_index = self.find_channel_index_by_id(
                    selected_data.channel_id
                )
                self.is_filtered = False
            else:
                self.parent_index = self.index

            self.index = 0
            self.scroll_top = 0
        elif self.page_state == PageState.ENTRIES and isinstance(selected_data, Entry):
            self.play(selected_data)
            if not selected_data.is_viewed:
                self.mark_as_watched()
        elif self.page_state == PageState.RESTORING and isinstance(
            selected_data, Channel
        ):
            if ch in (Key.l, Key.o, curses.KEY_RIGHT):
                if self.enter_restore_entries():
                    self.scroll_top = 0
                return
            if not self.restore_channel(selected_data):
                return
            self.page_state = PageState.CHANNELS
            if self.is_filtered:
                self.reset_filter()
            self.enter_restore()
        elif self.page_state == PageState.RESTORING_ENTRIES and isinstance(
            selected_data, Entry
        ):
            self.toggle_is_deleted(selected_data)
        elif self.page_state == PageState.TAGS and isinstance(selected_data, Tag):
            if self.is_filtered:
                self.reset_filter()
                self.index = self.find_tag_index(selected_data.title)
            self.select_tag(selected_data)
        elif self.page_state == PageState.TAGS_CHANNELS and isinstance(
            selected_data, Channel
        ):
            if selected_data.entries_count == 0:
                return
            if self.is_filtered:
                self.reset_filter()
            self.parent_index = self.find_channel_index_by_id(selected_data.channel_id)
            self.lines = self.get_lines_by_id(selected_data.channel_id)
            self.page_state = PageState.ENTRIES
            self.index = 0
            self.scroll_top = 0

    def move_back_to_channels(self) -> None:
        if self.is_channels_outdated:
            self.update_channels()
        self.page_state = PageState.CHANNELS
        self.lines = list(map(Line, self.channels))
        self.index = max(self.parent_index, 0)
        self.parent_index_restore = -1
        self.parent_index_tags = -1
        self.scroll_top = 0
        self.gravity = Gravity.DOWN
        self._is_feed_opened = False

    @property
    def status(self) -> str:
        title = ""
        if self.page_state == PageState.ENTRIES:
            title = self.channels[self.parent_index].title
        if self.is_filtered:
            title = "%d found" % len(self.lines)
        if (
            self.page_state == PageState.RESTORING
            or self.page_state == PageState.RESTORING_ENTRIES
        ):
            title = "RESTORING"
        elif self.page_state == PageState.TAGS:
            title = "TAGS"
        elif self.page_state == PageState.TAGS_CHANNELS and self.parent_index_tags > -1:
            title = self.tag_by_index(self.parent_index_tags).title

        return " ".join(
            self.c.status_fmt.format(
                msg=self.status_msg,
                index=self.status_index(lines_count=len(self.lines)),
                title=title,
                keybinds=self.status_keybinds,
                last_update=self.status_last_update,
            ).split()
        )

    def filter_lines(self, keyword: str) -> None:
        condition = lambda v: keyword.lower() in v.data.title.lower()
        self.lines = list(filter(condition, self.lines))
        self.index = 0
        self.scroll_top = 0
        self.gravity = Gravity.DOWN
        self.is_filtered = True

    def reset_filter(self) -> None:
        self.scroll_top = 0
        self.gravity = Gravity.DOWN
        self._reset_filter()

    def jump(self, keyword: str) -> None:
        try:
            key_index = int(keyword)
        except:
            return
        if (key_index - 1) not in range(len(self.lines)):
            return
        self.index = key_index - 1
        self.gravity = Gravity.DOWN

    def handle_input(
        self,
        screen: curses.window,
        cli_type: CLIType = CLIType.FILTER,
        prefix: str = "/",
        n: int | None = None,
    ) -> bool | None:
        keyword = ""
        if cli_type is CLIType.JUMP:
            if n is None:
                return
            num = n - 48
            if num > 9 or num < 1:
                return
            prefix = ":"
            keyword = f"{num}"

        curses.curs_set(1)
        max_y, max_x = screen.getmaxyx()
        if self.statusbar_height:
            screen.addnstr(
                max_y - 2,
                0,
                f"{self.status:<{max_x}}",
                max_x,
                curses.color_pair(ColorPair.ACTIVE),
            )
        screen.move(max_y - 1, 0)
        screen.clrtoeol()
        screen.addstr(max_y - 1, 1, prefix)
        screen.addnstr(max_y - 1, len(prefix) + 1, keyword, 1)
        screen.move(max_y - 1, len(prefix) + 1 + len(keyword))
        screen.refresh()
        try:
            while ch := screen.getch():
                screen.refresh()
                max_y, max_x = screen.getmaxyx()
                if cli_type is CLIType.CONFIRM:
                    screen.clear()
                    curses.curs_set(0)
                    return chr(ch).lower() == "y"
                if ch == 10:
                    screen.clear()
                    curses.curs_set(0)
                    if not keyword:
                        return
                    if cli_type is CLIType.JUMP:
                        self.jump(keyword)
                    else:
                        self.filter_lines(keyword)
                    return
                if ch == Key.ESC:
                    screen.clear()
                    return
                if ch == curses.KEY_BACKSPACE:
                    if not len(keyword):
                        continue
                    keyword = keyword[: len(keyword) - 1]
                    screen.move(max_y - 1, len(prefix) + max(1, len(keyword)))
                    screen.clrtoeol()
                    screen.refresh()
                else:
                    keyword += chr(ch)
                width = min(len(keyword), max_x - 3)
                screen.addnstr(max_y - 1, len(prefix) + 1, keyword, max(1, width))
        except KeyboardInterrupt:
            return


def main():
    args = tui_args.parse_args()
    config = Config(config_file=args.config, channels_filepath=args.channels_file)
    config.tui.update(vars(args))

    if not config.storage_path.parent.exists():
        config.storage_path.parent.mkdir(parents=True)

    if args.debug:
        config.logger.file = None
        config.logger.stream = True
        config.logger.level = LogLevel.DEBUG
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
