import asyncio
import curses
from enum import Enum, IntEnum, auto
import re
import subprocess as sp
from typing import Literal
import sys

from pytfeeder import Config, Feeder, Storage, utils, __version__
from pytfeeder.logger import init_logger
from pytfeeder.models import Channel, Entry
from pytfeeder.tui import args as tui_args, ConfigTUI
from pytfeeder.tui.props import TuiProps, PageState, Line


class Key(IntEnum):
    j = ord("j")
    J = ord("J")
    k = ord("k")
    K = ord("K")
    g = ord("g")
    G = ord("G")
    q = ord("q")
    l = ord("l")
    h = ord("h")
    a = ord("a")
    A = ord("A")
    p = ord("p")
    n = ord("n")
    c = ord("c")
    r = ord("r")
    d = ord("d")
    D = ord("D")
    f = ord("f")
    s = ord("s")
    F1 = 265
    F2 = 266
    F3 = 267
    F4 = 268
    N1 = ord("1")
    N2 = ord("2")
    N3 = ord("3")
    N4 = ord("4")
    N5 = ord("5")
    N6 = ord("6")
    N7 = ord("7")
    N8 = ord("8")
    N9 = ord("9")
    CTRL_D = 4
    TAB = 9
    SLASH = ord("/")
    CTRL_X = 24
    ESC = 27
    RETURN = ord("\n")
    QUESTION_MARK = ord("?")


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

    def _start(self, screen: "curses._CursesWindow") -> None:
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

    def run_loop(self, screen: "curses._CursesWindow") -> None:
        while True:
            self.draw(screen)
            ch = screen.getch()
            match ch:
                case Key.j | curses.KEY_DOWN | Key.TAB | Key.n:
                    if len(self.lines) > 0:
                        self.move_down()
                case Key.k | curses.KEY_UP | curses.KEY_BTAB | Key.p:
                    if len(self.lines) > 0:
                        self.move_up()
                case Key.l | curses.KEY_RIGHT | Key.RETURN:
                    if len(self.lines) > 0:
                        screen.clear()
                        self.move_right()
                case Key.h | curses.KEY_LEFT:
                    if len(self.lines) > 0:
                        screen.clear()
                    if self.is_filtered:
                        self.reset_filter()
                        self.draw(screen)
                    elif self.page_state == PageState.CHANNELS:
                        sys.exit(0)
                    elif self.page_state == PageState.ENTRIES:
                        self.move_back_to_channels()
                    screen.refresh()
                case Key.r:
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
                case Key.f:
                    if self.handle_follow():
                        screen.clear()
                case Key.QUESTION_MARK:
                    self.open_help(screen)
                case Key.d:
                    self.download()
                case Key.D:
                    self.download_all()
                case Key.CTRL_X | curses.KEY_DC:
                    if self.mark_as_deleted():
                        screen.clear()
                case Key.s:
                    self.c.hide_statusbar = not self.c.hide_statusbar
                    max_y, _ = screen.getmaxyx()
                    self.gravity = Gravity.UP
                    self.update_scroll_top(max_rows=max_y - self.statusbar_height)
                    screen.clear()
                case Key.c:
                    screen.clear()
                case Key.q:
                    sys.exit(0)

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

        self.status_msg = f"executing {macro!r}..."
        sp.Popen(
            [macro, selected_data.id, selected_data.title],
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
        )

    def draw(self, screen: "curses._CursesWindow") -> None:
        x = 0  # y = 0
        max_y, max_x = screen.getmaxyx()
        max_rows = max_y - self.statusbar_height
        self.update_scroll_top(max_rows)
        self.update_active()
        index_len = len(str(len(self.lines)))
        for i, line in enumerate(
            self.lines[self.scroll_top : self.scroll_top + max_rows]
        ):
            attr = None
            color = ColorPair.NONE
            text = "-"
            index = f"{i + 1 + self.scroll_top:{index_len}d}"
            highlight = False

            if isinstance(line.data, Entry):
                highlight = not line.data.is_viewed
                published = line.data.published.strftime(self.c.datetime_fmt)
                text = self.current_entry_format.format(
                    index=index,
                    new_mark=self.new_marks[highlight],
                    published=published,
                    title=line.data.title,
                    channel_title=self.channel_title(line.data.channel_id),
                )

            elif isinstance(line.data, Channel):
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

            if highlight and line.is_active:
                color = ColorPair.ACTIVE
                attr = curses.A_BOLD
            elif line.is_active:
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

    def update_active(self) -> None:
        for i in range(len(self.lines)):
            self.lines[i].is_active = i == self.index

    def open_help(self, screen: "curses._CursesWindow") -> None:
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

        channel_id = self.lines[self.index].data.channel_id
        self.parent_index = self.find_channel_index_by_id(channel_id)
        self.is_filtered = False
        self.lines = self.get_lines_by_id(channel_id)
        self.index = 0
        self.scroll_top = 0
        return True

    def move_right(self) -> None:
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
            utils.play_video(selected_data)
            if not selected_data.is_viewed:
                self.mark_as_watched()

    def move_back_to_channels(self) -> None:
        if self.is_channels_outdated:
            self.update_channels()
        self.page_state = PageState.CHANNELS
        self.lines = list(map(Line, self.channels))
        self.index = self.parent_index
        self.scroll_top = 0
        self.gravity = Gravity.DOWN

    @property
    def status(self) -> str:
        title = ""
        if self.page_state == PageState.ENTRIES:
            title = self.channels[self.parent_index].title
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

    def filter_lines(self, keyword: str) -> None:
        condition = lambda v: keyword.lower() in v.data.title.lower()
        self.lines = list(filter(condition, self.lines))
        self.index = 0
        self.scroll_top = 0
        self.gravity = Gravity.DOWN
        self.is_filtered = True

    def reset_filter(self) -> None:
        self.is_filtered = False
        self.index = 0
        self.scroll_top = 0
        self.gravity = Gravity.DOWN
        if self.page_state == PageState.CHANNELS:
            self.lines = list(map(Line, self.channels))
        elif self.page_state == PageState.ENTRIES:
            selected_data = self.channels[self.parent_index]
            self.lines = self.get_lines_by_id(selected_data.channel_id)

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
        screen: "curses._CursesWindow",
        cli_type: CLIType = CLIType.FILTER,
        n: int | None = None,
    ) -> None:
        prefix = "/"
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
        screen.move(max_y - 1, 2)
        screen.addch(prefix)
        screen.addnstr(max_y - 1, 3, keyword, 1)
        screen.refresh()
        try:
            while ch := screen.getch():
                screen.refresh()
                max_y, max_x = screen.getmaxyx()
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
                if ch in (Key.SLASH, Key.ESC):
                    screen.clear()
                    return
                if ch == curses.KEY_BACKSPACE:
                    if not len(keyword):
                        continue
                    keyword = keyword[: len(keyword) - 1]
                    screen.addnstr(max_y - 1, 3, " " * max_x, max_x - 4)
                    screen.refresh()
                else:
                    keyword += chr(ch)
                width = min(len(keyword), max_x - 3)
                screen.addnstr(max_y - 1, 3, keyword, width or 1)
        except KeyboardInterrupt:
            return


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

    try:
        _ = App(feeder).start()
    except Exception as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
