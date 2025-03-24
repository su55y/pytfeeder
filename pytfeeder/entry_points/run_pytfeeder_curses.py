import asyncio
import curses
from dataclasses import dataclass
from enum import Enum, IntEnum, auto
import subprocess as sp
import time
from typing import List, Literal, Optional, Union

from pytfeeder.feeder import Feeder
from pytfeeder.config import Config
from pytfeeder.models import Channel, Entry
from pytfeeder.storage import Storage
from pytfeeder.utils import download_video, download_all, play_video
from pytfeeder.tui.args import parse_args
from pytfeeder.tui.updater import Updater
from pytfeeder.tui.props import TuiProps, PageState


@dataclass
class Line:
    data: Union[Channel, Entry]
    is_active: bool = False


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
    TAB = 9
    SLASH = ord("/")
    ESC = 27
    RETURN = ord("\n")
    QUESTION_MARK = ord("?")


class Gravity(Enum):
    DOWN = auto()
    UP = auto()


class Color(IntEnum):
    NONE = 0
    ACTIVE = 1
    NEW = 2


class CLIType(Enum):
    FILTER = auto()
    JUMP = auto()


class App(TuiProps):
    def __init__(self, feeder: Feeder, updater: Updater) -> None:
        self.updater = updater
        super().__init__(feeder)
        self._set_channels()
        self.refresh_last_update()
        if "{unwatched_count}" in self.c.channels_fmt:
            self.unwatched_method = lambda c_id: self.feeder.unwatched_count(c_id)

        self.gravity = Gravity.DOWN
        self.is_pad_active = False
        self.last_channel_index = -1
        self.last_page_index = -1
        self.lines = list(map(Line, self.channels))
        self.max_len_chan_title = max(len(c.title) for c in self.channels)
        self.scroll_top = 0
        self.selected_data = None
        self._g_pressed = False
        self.macros = {
            Key.F1: self.c.macro1,
            Key.F2: self.c.macro2,
            Key.F3: self.c.macro3,
            Key.F4: self.c.macro4,
        }
        if msg := self.updater.status_msg:
            self.status_msg = msg
            self.status_msg_lifetime = time.perf_counter()

    def start(self) -> None:
        curses.wrapper(self._start)

    def _start(self, screen: "curses._CursesWindow") -> None:
        self.config_curses()
        try:
            self.run_loop(screen)
        except KeyboardInterrupt:
            pass

    def config_curses(self) -> None:
        try:
            curses.use_default_colors()
            curses.curs_set(0)
            curses.init_pair(Color.ACTIVE, curses.COLOR_BLACK, curses.COLOR_YELLOW)
            curses.init_pair(Color.NEW, curses.COLOR_YELLOW, -1)
        except:
            curses.initscr()

    def run_loop(self, screen: "curses._CursesWindow") -> None:
        while True:
            self.draw(screen)
            ch = screen.getch()
            self.status_msg = ""
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
                    match self.page_state:
                        case PageState.CHANNELS:
                            if not self.is_filtered:
                                exit(0)
                            self.move_left_channels()
                            self.draw(screen)
                            screen.refresh()
                        case PageState.ENTRIES:
                            self.move_left_entries()
                        case _:
                            continue
                    if self.is_filtered:
                        self.is_filtered = False
                case Key.r:
                    self.status_msg = "updating..."
                    self.status_msg_lifetime = time.perf_counter()
                    self.draw(screen)
                    self.reload()
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
                    if self.page_state == PageState.ENTRIES and not self.is_filtered:
                        self.move_next()
                        screen.clear()
                case Key.K:
                    if self.page_state == PageState.ENTRIES and not self.is_filtered:
                        self.move_prev()
                        screen.clear()
                case Key.f:
                    if self.handle_follow():
                        screen.clear()
                case Key.QUESTION_MARK:
                    self.open_help(screen)
                case Key.d:
                    if self.page_state != PageState.ENTRIES:
                        continue
                    if len(self.lines) == 0:
                        continue
                    selected_data = self.lines[self.index].data
                    if not isinstance(selected_data, Entry):
                        raise Exception(
                            "unexpected selected data type %s: %r"
                            % (type(selected_data), selected_data)
                        )
                    err = download_video(selected_data)
                    if err:
                        self.status_msg = f"download failed: {err}"
                        self.status_msg_lifetime = time.perf_counter()
                    else:
                        if not selected_data.is_viewed:
                            self.mark_as_watched()
                case Key.D:
                    self.selected_data = self.lines[self.index].data
                    if not (
                        self.page_state == PageState.ENTRIES
                        and isinstance(self.selected_data, Entry)
                    ):
                        continue

                    entries = [l.data for l in self.lines if l.data.is_viewed is False]  # type: ignore
                    if len(entries) > 0:
                        download_all(entries)  # type: ignore
                    self.mark_as_watched_all()

                case Key.c:
                    screen.clear()
                case Key.q:
                    exit(0)

    def handle_macro(self, key: Literal[Key.F1, Key.F2, Key.F3, Key.F4]) -> None:
        if self.page_state != PageState.ENTRIES:
            return
        if len(self.lines) == 0:
            return
        macro = self.macros.get(key)
        if not macro or len(macro) == 0:
            return

        self.selected_data = self.lines[self.index].data
        if not isinstance(self.selected_data, Entry):
            return

        self.status_msg = f"Executing macro {Key(key).name}..."
        self.status_msg_lifetime = time.perf_counter()
        sp.Popen(
            [macro, self.selected_data.id, self.selected_data.title],
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
        )

    def draw(self, screen: "curses._CursesWindow") -> None:
        x, y = 0, 0
        max_y, max_x = screen.getmaxyx()
        max_rows = max_y - y - 1
        self.update_scroll_top(max_rows)
        self.update_active()
        index_len = len(str(len(self.lines)))
        for i, line in enumerate(
            self.lines[self.scroll_top : self.scroll_top + max_rows]
        ):
            color_pair = Color.NONE
            text = "-"
            index = f"{i + 1 + self.scroll_top:{index_len}d}"

            if isinstance(line.data, Entry):
                if line.data.is_viewed is False:
                    color_pair = Color.NEW
                published = line.data.published.strftime(self.c.datetime_fmt)
                text = self.current_entry_format.format(
                    index=index,
                    new_mark=self.new_marks[not line.data.is_viewed],
                    published=published,
                    title=line.data.title,
                    channel_title=f"{self.feeder.channel_title(line.data.channel_id):^{self.max_len_chan_title}s}",
                )

            elif isinstance(line.data, Channel):
                if line.data.have_updates:
                    color_pair = Color.NEW
                text = self.c.channels_fmt.format(
                    index=index,
                    new_mark=self.new_marks[line.data.have_updates],
                    title=line.data.title,
                    unwatched_count=self.unwatched_method(line.data.channel_id),
                )

            if line.is_active:
                color_pair = Color.ACTIVE

            text = f"{text:<{max_x}}"
            screen.addnstr(y, x, text, max_x, curses.color_pair(color_pair))
            y += 1

        try:
            screen.addnstr(
                max_y - 1,
                x,
                f"{self.status:<{max_x}}",
                max_x,
                curses.color_pair(Color.ACTIVE),
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
            pad.addnstr(i, 0, text, min(len(text), max_x), curses.color_pair(2))

        pad.addnstr(len(self.help_lines), 0, "~", 1, curses.color_pair(2))

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
                    curses.color_pair(Color.ACTIVE),
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

    def move(self, channel_index: int) -> None:
        self.last_channel_index = channel_index
        self.last_page_index = channel_index
        self.lines = self.lines_by_id(self.channels[channel_index].channel_id)
        self.index = 0
        self.scroll_top = 0

    def move_next(self) -> None:
        if self.last_channel_index == len(self.channels) - 1:
            self.move(0)
        else:
            self.move(min(len(self.channels) - 1, self.last_channel_index + 1))

    def move_prev(self) -> None:
        if self.last_channel_index == 0:
            self.move(len(self.channels) - 1)
        else:
            self.move(max(0, self.last_channel_index - 1))

    def handle_follow(self) -> bool:
        if (
            self.page_state != PageState.ENTRIES
            or not self._is_feed_opened
            or self.last_channel_index != 0
        ):
            return False
        new_last_channel_index = -1
        for i in range(len(self.channels)):
            if self.channels[i].channel_id == self.lines[self.index].data.channel_id:
                new_last_channel_index = i
                break
        if new_last_channel_index < 1:
            return False
        self.lines = self.lines_by_id(self.lines[self.index].data.channel_id)
        self.last_channel_index = new_last_channel_index
        self.last_page_index = new_last_channel_index
        self.index = 0
        self.scroll_top = 0
        return True

    def move_right(self, last_channel_index: int = -1) -> None:
        if last_channel_index > -1:
            self.selected_data = self.channels[last_channel_index]
        else:
            self.selected_data = self.lines[self.index].data

        if self.page_state == PageState.CHANNELS:
            self.page_state = PageState.ENTRIES
            self.is_filtered = False
            if last_channel_index == -1:
                self.last_page_index = self.index
            self.lines = self.lines_by_id(self.selected_data.channel_id)
            self.last_channel_index = self.index
            self.index = 0
            self.scroll_top = 0
        elif self.page_state == PageState.ENTRIES:
            if not isinstance(self.selected_data, Entry):
                raise Exception(
                    "unexpected selected data type %s: %r"
                    % (type(self.selected_data), self.selected_data)
                )
            play_video(self.selected_data)
            if not self.selected_data.is_viewed:
                self.mark_as_watched()

    def move_left_channels(self) -> None:
        self.lines = list(map(Line, self.channels))
        self.index = max(0, self.last_page_index)
        self.last_page_index = -1
        self.scroll_top = 0

    def move_left_entries(self) -> None:
        self.page_state = PageState.CHANNELS
        if not self.is_filtered:
            self.lines = list(map(Line, self.channels))
            self.index = min(self.last_page_index, len(self.lines) - 1)
            self.last_page_index = -1
            self.scroll_top = 0
            self.gravity = Gravity.DOWN
        else:
            self.move_right(self.last_channel_index)
            self.last_channel_index = self.last_page_index

    def reload(self) -> None:
        after = 0
        before = self.feeder.unwatched_count()
        if self.page_state == PageState.ENTRIES and self.selected_data.channel_id != "feed":  # type: ignore
            before = self.feeder.unwatched_count(self.selected_data.channel_id)  # type: ignore

        try:
            asyncio.run(self.feeder.sync_entries())
        except:
            self.status_msg = "reload failed"
            self.status_msg_lifetime = time.perf_counter()
            return

        self.update_channels()
        if self.page_state == PageState.CHANNELS:
            self.lines = list(map(Line, self.channels))
            after = self.feeder.unwatched_count()
        elif self.page_state == PageState.ENTRIES:
            self.index = 0
            self.lines = self.lines_by_id(
                channel_id=self.channels[self.last_channel_index].channel_id
            )
            if self.selected_data.channel_id == "feed":  # type: ignore
                after = self.feeder.unwatched_count()
            else:
                after = self.feeder.unwatched_count(self.selected_data.channel_id)  # type: ignore

        new = after - before
        if max(new, 0) > 0:
            self.status_msg = f"{new} new updates"
        else:
            self.status_msg = "no updates"
        self.status_msg_lifetime = time.perf_counter()

        self.updater.update_lock_file()
        self.refresh_last_update()

    def filter_lines(self, keyword: str) -> None:
        if not keyword:
            return
        keyword = keyword.lower()
        self.lines = list(filter(lambda v: keyword in v.data.title.lower(), self.lines))
        if self.page_state == PageState.CHANNELS:
            self.last_page_index = self.index
        self.index = 0
        self.scroll_top = 0
        self.gravity = Gravity.DOWN
        self.is_filtered = True
        curses.curs_set(0)

    def jump(self, key_index: int) -> None:
        if key_index > len(self.lines) + 1:
            return
        self.index = key_index - 1
        self.gravity = Gravity.DOWN
        curses.curs_set(0)

    def handle_input(
        self,
        screen: "curses._CursesWindow",
        cli_type: CLIType = CLIType.FILTER,
        n: Optional[int] = None,
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
        screen.addnstr(
            max_y - 2,
            0,
            f"{self.status:<{max_x}}",
            max_x,
            curses.color_pair(Color.ACTIVE),
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
                        try:
                            key_index = int(keyword)
                        except:
                            return
                        if key_index < 1:
                            return

                        self.jump(key_index)
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

    def mark_as_watched_all(self) -> None:
        self.selected_data = self.lines[self.index].data

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
            if self.channels[self.last_page_index].channel_id == "feed":
                unwatched = all(not c.have_updates for c in self.channels)
                self.feeder.mark_as_watched(unwatched=unwatched)
                for i in range(len(self.channels)):
                    self.channels[i].have_updates = unwatched
                for i in range(len(self.lines)):
                    self.lines[i].data.is_viewed = not unwatched  # type: ignore
            else:
                unwatched = not self.channels[self.last_page_index].have_updates
                self.feeder.mark_as_watched(
                    channel_id=self.selected_data.channel_id, unwatched=unwatched
                )
                self.channels[self.last_page_index].have_updates = unwatched
                for i in range(len(self.lines)):
                    self.lines[i].data.is_viewed = not unwatched  # type: ignore

    def mark_as_watched(self) -> None:
        self.selected_data = self.lines[self.index].data
        if self.page_state == PageState.CHANNELS and isinstance(
            self.selected_data, Channel
        ):
            if self.selected_data.channel_id == "feed":
                return
            unwatched = not self.selected_data.have_updates
            self.feeder.mark_as_watched(
                channel_id=self.selected_data.channel_id, unwatched=unwatched
            )
            self.selected_data.have_updates = unwatched
        elif self.page_state == PageState.ENTRIES and isinstance(
            self.selected_data, Entry
        ):
            unwatched = self.selected_data.is_viewed
            self.feeder.mark_as_watched(id=self.selected_data.id, unwatched=unwatched)
            self.selected_data.is_viewed = not unwatched
            self.move_down()

    @property
    def status(self) -> str:
        return self._format_status()

    def _format_status(self) -> str:
        title = ""
        if self.last_page_index > -1 and len(self.channels) >= self.last_page_index + 1:
            title = "%s " % self.channels[self.last_page_index].title
        if self.is_filtered:
            title = "%d found " % len(self.lines)
        if (
            len(self.status_msg) > 0
            and (time.perf_counter() - self.status_msg_lifetime) > 3
        ):
            self.status_msg = ""
            self.status_msg_lifetime = 0

        return " ".join(
            self.c.status_fmt.format(
                msg=self.status_msg,
                index=self.status_index,
                title=title,
                keybinds=self.status_keybinds,
                last_update=self.status_last_update,
            ).split()
        )

    @property
    def status_index(self) -> str:
        num_fmt = f"%{len(str(len(self.lines)))}d"
        index = self.index + 1
        if self.is_filtered and len(self.lines) == 0:
            index = 0
        return "[%s/%s] " % ((num_fmt % index), (num_fmt % len(self.lines)))

    def lines_by_id(self, channel_id: str) -> List[Line]:
        if channel_id == "feed":
            self._is_feed_opened = True
            return list(map(Line, self.feed()))
        self._is_feed_opened = False
        return list(map(Line, self.channel_feed(channel_id)))


def main():
    args = parse_args()
    config_path = args.config
    config = Config(config_path)
    if not config:
        exit(1)
    if not config.storage_path.parent.exists():
        config.storage_path.parent.mkdir(parents=True)

    config.tui.update(vars(args))

    feeder = Feeder(config, Storage(config.storage_path))
    if len(feeder.channels) == 0:
        print(f"No channels found in config {config_path}")
        exit(0)

    updater = Updater(feeder)

    try:
        _ = App(feeder, updater).start()
    except Exception as e:
        print(e)
        exit(1)


if __name__ == "__main__":
    main()
