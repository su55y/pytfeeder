import asyncio
import curses
from dataclasses import dataclass
import datetime as dt
from enum import Enum, IntEnum, auto
import subprocess as sp
import time
from typing import List, Literal, Optional, Union

from pytfeeder.feeder import Feeder
from pytfeeder.config import Config
from pytfeeder.models import Channel, Entry
from pytfeeder.storage import Storage
from pytfeeder.tui.args import parse_args, format_keybindings
from pytfeeder.tui.consts import DEFAULT_KEYBINDS, DEFAULT_LOCK_FILE
from pytfeeder.tui.updater import Updater


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


def notify(msg: str) -> bool:
    if not msg:
        return True
    cmd = ["notify-send", "-i", "youtube", "-a", "pytfeeder", msg]
    p = sp.run(cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    if p.returncode != 0:
        return False
    return True


def download_video(entry: Entry, send_notification=True) -> Optional[str]:
    p = sp.check_output(
        [
            "tsp",
            "yt-dlp",
            f"https://youtu.be/{entry.id}",
            "-o",
            "~/Videos/YouTube/%(uploader)s/%(title)s.%(ext)s",
        ],
        shell=False,
    )

    if send_notification:
        _ = notify(f"⬇️Start downloading {entry.title!r}...")

    _ = sp.run(
        [
            "tsp",
            "-D",
            p.decode(),
            "notify-send",
            "-i",
            "youtube",
            "-a",
            "pytfeeder",
            f"✅Download done: {entry.title}",
        ],
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL,
    )


def download_all(entries: List[Entry]) -> Optional[str]:
    _ = notify(f"⬇️Start downloading {len(entries)} entries...")
    for e in entries:
        download_video(e, send_notification=False)


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


class PageState(Enum):
    CHANNELS = auto()
    ENTRIES = auto()


class CLIType(Enum):
    FILTER = auto()
    JUMP = auto()


class App:
    def __init__(self, feeder: Feeder, updater: Updater) -> None:
        self.feeder = feeder
        self.c = self.feeder.config.tui
        self.channels = list()
        self._set_channels()
        self.updater = updater

        self.filtered = False
        self.gravity = Gravity.DOWN
        self.index = 0
        self.is_pad_active = False
        self.keybinds_str = DEFAULT_KEYBINDS
        self.last_channel_index = -1
        self.last_page_index = -1
        self.lines = list(map(Line, self.channels))
        self.max_len_chan_title = max(len(c.title) for c in self.channels)
        self.scroll_top = 0
        self.selected_data = None
        self.state = PageState.CHANNELS
        self._g_pressed = False
        self.help_lines = list(map(lambda s: s.lstrip(), format_keybindings()))
        self._status_msg = ""
        self._status_msg_time = 0
        self._is_feed = False
        self.macros = {
            Key.F1: self.c.macro1,
            Key.F2: self.c.macro2,
            Key.F3: self.c.macro3,
            Key.F4: self.c.macro4,
        }
        self._last_update = ""
        self.refresh_last_update()
        if msg := self.updater.status_msg:
            self._status_msg = msg
            self._status_msg_time = time.perf_counter()

    def _set_channels(self, channels: List[Channel] = list()) -> None:
        if channels:
            self.feeder.channels = channels

        if self.feeder.config.alphabetic_sort:
            self.feeder.channels.sort(key=lambda c: c.title)

        if self.c.hide_feed:
            self.channels = self.feeder.channels
        else:
            feed_channel = Channel(
                title="Feed",
                channel_id="feed",
                have_updates=bool(self.feeder.unviewed_count()),
            )
            self.channels = [feed_channel, *self.feeder.channels]

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
            self._status_msg = ""
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
                    match self.state:
                        case PageState.CHANNELS:
                            if not self.filtered:
                                exit(0)
                            self.move_left_channels()
                            self.draw(screen)
                            screen.refresh()
                        case PageState.ENTRIES:
                            self.move_left_entries()
                        case _:
                            continue
                    if self.filtered:
                        self.filtered = False
                case Key.r:
                    self._status_msg = "updating..."
                    self._status_msg_time = time.perf_counter()
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
                    self.mark_viewed()
                case Key.A:
                    self.mark_viewed_all()
                case Key.J:
                    if self.state == PageState.ENTRIES and not self.filtered:
                        self.move_next()
                        screen.clear()
                case Key.K:
                    if self.state == PageState.ENTRIES and not self.filtered:
                        self.move_prev()
                        screen.clear()
                case Key.QUESTION_MARK:
                    self.switch_to_pad(screen)
                case Key.d:
                    if self.state != PageState.ENTRIES:
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
                        self._status_msg = f"download failed: {err}"
                        self._status_msg_time = time.perf_counter()
                    else:
                        if not selected_data.is_viewed:
                            self.mark_viewed()
                case Key.D:
                    self.selected_data = self.lines[self.index].data
                    if not (
                        self.state == PageState.ENTRIES
                        and isinstance(self.selected_data, Entry)
                    ):
                        continue

                    entries = [l.data for l in self.lines if l.data.is_viewed is False]  # type: ignore
                    if len(entries) > 0:
                        download_all(entries)  # type: ignore
                    self.mark_viewed_all()

                case Key.c:
                    screen.clear()
                case Key.q:
                    exit(0)

    def handle_macro(self, key: Literal[Key.F1, Key.F2, Key.F3, Key.F4]) -> None:
        if self.state != PageState.ENTRIES:
            return
        if len(self.lines) == 0:
            return
        macro = self.macros.get(key)
        if not macro or len(macro) == 0:
            return

        self.selected_data = self.lines[self.index].data
        if not isinstance(self.selected_data, Entry):
            return

        self._status_msg = f"Executing macro {Key(key).name}..."
        self._status_msg_time = time.perf_counter()
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
            new_mark = " " * len(self.c.new_mark)
            text = "-"
            index = f"{i + 1 + self.scroll_top:{index_len}d}"

            if isinstance(line.data, Entry):
                if line.data.is_viewed is False:
                    new_mark = self.c.new_mark
                    color_pair = Color.NEW
                updated = line.data.updated.strftime(self.feeder.config.datetime_fmt)
                fmt = self.c.feed_entries_fmt if self._is_feed else self.c.entries_fmt
                text = fmt.format(
                    index=index,
                    new_mark=new_mark,
                    updated=updated,
                    title=line.data.title,
                    channel_title=f"{self.feeder.channel_title(line.data.channel_id):^{self.max_len_chan_title}s}",
                )

            elif isinstance(line.data, Channel):
                if line.data.have_updates:
                    new_mark = self.c.new_mark
                    color_pair = Color.NEW
                text = self.c.channels_fmt.format(
                    index=index, new_mark=new_mark, title=line.data.title
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

    def switch_to_pad(self, screen: "curses._CursesWindow") -> None:
        screen.clear()
        max_y, max_x = screen.getmaxyx()
        pad_pos = 0
        pad = curses.newpad(len(self.help_lines) + 1, max_x)
        help_status = " Help [j,Down,k,Up]: navigate, [h,q,Left]: close help"

        def draw_pad():
            for i, line in enumerate(self.help_lines):
                text = f"{line}"
                pad.addnstr(i, 0, text, min(len(text), max_x), curses.color_pair(2))
            pad.addnstr(len(self.help_lines), 0, "~", 1, curses.color_pair(2))

        draw_pad()
        pad.refresh(pad_pos, 0, 0, 0, max_y - 2, max_x - 1)
        screen.refresh()

        while True:
            max_y, max_x = screen.getmaxyx()
            pad.refresh(pad_pos, 0, 0, 0, max_y - 2, max_x - 1)
            try:
                screen.addnstr(
                    max_y - 1,
                    0,
                    f"{help_status:<{max_x}}",
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

    def move_next(self) -> None:
        if self.last_channel_index == len(self.channels) - 1:
            channel_index = 0
        else:
            channel_index = min(len(self.channels) - 1, self.last_channel_index + 1)
        self.last_channel_index = channel_index
        self.last_page_index = channel_index
        self.lines = self.lines_by_id(self.channels[channel_index].channel_id)
        self.index = 0
        self.scroll_top = 0

    def move_prev(self) -> None:
        if self.last_channel_index == 0:
            channel_index = len(self.channels) - 1
        else:
            channel_index = max(0, self.last_channel_index - 1)
        self.last_channel_index = channel_index
        self.last_page_index = channel_index
        self.lines = self.lines_by_id(self.channels[channel_index].channel_id)
        self.index = 0
        self.scroll_top = 0

    def move_right(self, last_channel_index: int = -1) -> None:
        if last_channel_index > -1:
            self.selected_data = self.channels[last_channel_index]
        else:
            self.selected_data = self.lines[self.index].data

        if self.state == PageState.CHANNELS:
            self.state = PageState.ENTRIES
            self.filtered = False
            if last_channel_index == -1:
                self.last_page_index = self.index
            self.lines = self.lines_by_id(self.selected_data.channel_id)
            self.last_channel_index = self.index
            self.index = 0
            self.scroll_top = 0
        elif self.state == PageState.ENTRIES:
            if not isinstance(self.selected_data, Entry):
                raise Exception(
                    "unexpected selected data type %s: %r"
                    % (type(self.selected_data), self.selected_data)
                )
            play_video(self.selected_data.id)
            if not self.selected_data.is_viewed:
                self.mark_viewed()
            notify(f"{self.selected_data.title} playing...")

    def move_left_channels(self) -> None:
        self.lines = list(map(Line, self.channels))
        self.index = max(0, self.last_page_index)
        self.last_page_index = -1
        self.scroll_top = 0

    def move_left_entries(self) -> None:
        self.state = PageState.CHANNELS
        if not self.filtered:
            self.lines = list(map(Line, self.channels))
            self.index = min(self.last_page_index, len(self.lines) - 1)
            self.last_page_index = -1
            self.scroll_top = 0
        else:
            self.move_right(self.last_channel_index)
            self.last_channel_index = self.last_page_index

    def reload(self) -> None:
        after = 0
        before = self.feeder.unviewed_count()
        if self.state == PageState.ENTRIES and self.selected_data.channel_id != "feed":  # type: ignore
            before = self.feeder.unviewed_count(self.selected_data.channel_id)  # type: ignore

        try:
            asyncio.run(self.feeder.sync_entries())
        except:
            self._status_msg = "reload failed"
            self._status_msg_time = time.perf_counter()
            return

        self._set_channels(self.feeder.update_channels())
        if self.state == PageState.CHANNELS:
            self.lines = list(map(Line, self.channels))
            after = self.feeder.unviewed_count()
        elif self.state == PageState.ENTRIES:
            self.index = 0
            self.lines = self.lines_by_id(
                channel_id=self.channels[self.last_channel_index].channel_id
            )
            if self.selected_data.channel_id == "feed":  # type: ignore
                after = self.feeder.unviewed_count()
            else:
                after = self.feeder.unviewed_count(self.selected_data.channel_id)  # type: ignore

        new = after - before
        if max(new, 0) > 0:
            self._status_msg = f"{new} new updates"
        else:
            self._status_msg = "no updates"
        self._status_msg_time = time.perf_counter()

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

    def filter_lines(self, keyword: str) -> None:
        if not keyword:
            return
        keyword = keyword.lower()
        self.lines = list(filter(lambda v: keyword in v.data.title.lower(), self.lines))
        if self.state == PageState.CHANNELS:
            self.last_page_index = self.index
        self.index = 0
        self.scroll_top = 0
        self.gravity = Gravity.DOWN
        self.filtered = True
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

    def mark_viewed_all(self) -> None:
        self.selected_data = self.lines[self.index].data

        if self.state == PageState.CHANNELS and isinstance(self.selected_data, Channel):
            self.feeder.mark_as_viewed(
                unviewed=all(not c.have_updates for c in self.feeder.channels)
            )
            self._set_channels(self.feeder.update_channels())
        elif self.state == PageState.ENTRIES and isinstance(self.selected_data, Entry):
            if self.channels[self.last_page_index].channel_id == "feed":
                unviewed = all(not c.have_updates for c in self.channels)
                self.feeder.mark_as_viewed(unviewed=unviewed)
                for i in range(len(self.channels)):
                    self.channels[i].have_updates = unviewed
                for i in range(len(self.lines)):
                    self.lines[i].data.is_viewed = not unviewed  # type: ignore
            else:
                unviewed = not self.channels[self.last_page_index].have_updates
                self.feeder.mark_as_viewed(
                    channel_id=self.selected_data.channel_id, unviewed=unviewed
                )
                self.channels[self.last_page_index].have_updates = unviewed
                for i in range(len(self.lines)):
                    self.lines[i].data.is_viewed = not unviewed  # type: ignore

    def mark_viewed(self) -> None:
        self.selected_data = self.lines[self.index].data
        if self.state == PageState.CHANNELS and isinstance(self.selected_data, Channel):
            if self.selected_data.channel_id == "feed":
                return
            unviewed = not self.selected_data.have_updates
            self.feeder.mark_as_viewed(
                channel_id=self.selected_data.channel_id, unviewed=unviewed
            )
            self.selected_data.have_updates = unviewed
        elif self.state == PageState.ENTRIES and isinstance(self.selected_data, Entry):
            unviewed = self.selected_data.is_viewed
            self.feeder.mark_as_viewed(id=self.selected_data.id, unviewed=unviewed)
            self.selected_data.is_viewed = not unviewed
            self.move_down()

    @property
    def status(self) -> str:
        return self._format_status()

    def _format_status(self) -> str:
        title = ""
        if self.last_page_index > -1 and len(self.channels) >= self.last_page_index + 1:
            title = "%s " % self.channels[self.last_page_index].title
        if self.filtered:
            title = "%d found " % len(self.lines)
        if (
            len(self._status_msg) > 0
            and (time.perf_counter() - self._status_msg_time) > 3
        ):
            self._status_msg = ""
            self._status_msg_time = 0

        return " ".join(
            self.c.status_fmt.format(
                msg=self._status_msg,
                index=self._status_index,
                title=title,
                keybinds=self._status_keybinds,
                last_update=self._last_update,
            ).split()
        )

    @property
    def _status_keybinds(self) -> str:
        keybinds_str = self.keybinds_str
        if self.filtered:
            keybinds_str = f"[h]: cancel filter, {keybinds_str}"
        return keybinds_str

    @property
    def _status_index(self) -> str:
        num_fmt = f"%{len(str(len(self.lines)))}d"
        index = self.index + 1
        if self.filtered and len(self.lines) == 0:
            index = 0
        return "[%s/%s] " % ((num_fmt % index), (num_fmt % len(self.lines)))

    def lines_by_id(self, channel_id: str) -> List[Line]:
        if channel_id == "feed":
            self._is_feed = True
            return list(map(Line, self.feeder.feed()))
        self._is_feed = False
        return list(map(Line, self.feeder.channel_feed(channel_id)))


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
    if args.update or config.tui.always_update or updater.is_update_interval_expired():
        print("Updating...")
        if err := updater.update():
            print("Update failed: %s" % err)
            exit(1)

    try:
        _ = App(feeder, updater).start()
    except Exception as e:
        print(e)
        exit(1)


if __name__ == "__main__":
    main()
