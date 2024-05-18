import argparse
import asyncio
import curses
from dataclasses import dataclass
import datetime as dt
from enum import Enum, IntEnum, auto
import os.path
import subprocess as sp
from typing import Union

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--channels-fmt",
        default=DEFAULT_CHANNELS_FMT,
        metavar="STR",
        help="channels format (default: %(default)r)",
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
    return parser.parse_args()


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
    SLASH = ord("/")
    ESC = 27
    RETURN = ord("\n")


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


class Picker:
    def __init__(
        self,
        feeder: Feeder,
        channels_fmt: str = DEFAULT_CHANNELS_FMT,
        entries_fmt: str = DEFAULT_ENTRIES_FMT,
        new_mark: str = DEFAULT_NEW_MARK,
    ) -> None:
        self.feeder = feeder
        self.channels = [
            Channel("Feed", "feed", have_updates=bool(self.feeder.unviewed_count())),
            *self.feeder.channels,
        ]

        self.channels_fmt = channels_fmt
        self.entries_fmt = entries_fmt
        self.gravity = Gravity.DOWN
        self.index = 0
        self.last_feed_index = -1
        self.lines = list(map(Line, self.channels))
        self.max_len_chan_title = max(len(c.title) for c in self.channels)
        self.new_mark = new_mark
        self.scroll_top = 0
        self.selected_data = None
        self.state = PageState.CHANNELS
        self._g_pressed = False
        self.filtered = False

    def start(self):
        curses.wrapper(self._start)

    def _start(self, screen: "curses._CursesWindow"):
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
            match screen.getch():
                case Key.j | curses.KEY_DOWN:
                    self.move_down()
                case Key.k | curses.KEY_UP:
                    self.move_up()
                case Key.l | curses.KEY_LEFT:
                    self.move_left()
                case Key.h | curses.KEY_RIGHT:
                    self.move_right()
                case Key.K:
                    self.move_top()
                case Key.g:
                    if self._g_pressed:
                        self.move_top()
                        self._g_pressed = False
                    else:
                        self._g_pressed = True
                case Key.G | Key.J:
                    self.move_bottom()
                case Key.SLASH:
                    self.handle_slash(screen)
                case Key.q | Key.ESC:
                    exit(0)

    def draw(self, screen: "curses._CursesWindow") -> None:
        screen.clear()
        x, y = 1, 0
        max_y, max_x = screen.getmaxyx()
        max_rows = max_y - y - 1
        n = max_x - 2
        self.update_scroll_top(max_rows)
        self.update_active()
        for line in self.lines[self.scroll_top : self.scroll_top + max_rows]:
            color_pair = Color.NONE
            new_mark = " " * len(self.new_mark)
            text = "-"

            if isinstance(line.data, Entry):
                if line.data.is_viewed is False:
                    new_mark = self.new_mark
                    color_pair = Color.NEW
                updated = line.data.updated.strftime("%b %d")
                text = self.entries_fmt.format(
                    new_mark=new_mark,
                    updated=updated,
                    title=line.data.title,
                    channel_title=f"{self.feeder.channel_title(line.data.channel_id):^{self.max_len_chan_title}s}",
                )
            elif isinstance(line.data, Channel):
                if line.data.have_updates:
                    new_mark = self.new_mark
                    color_pair = Color.NEW
                text = self.channels_fmt.format(new_mark=new_mark, title=line.data.title)
                
            if line.is_active:
                text = f"{text:<{n}}"
                color_pair = Color.ACTIVE

            screen.addnstr(y, x, text, n, curses.color_pair(color_pair))
            y += 1

        screen.addnstr(
            max_y - 1, x, f"{self.status:<{n}}", n, curses.color_pair(Color.ACTIVE)
        )
        screen.refresh()

    def update_scroll_top(self, max_rows: int) -> None:
        match self.gravity:
            case Gravity.DOWN:
                if (self.index + 1) - self.scroll_top > max_rows:
                    self.scroll_top = (self.index + 1) - max_rows
                if self.index + 1 < self.scroll_top:
                    self.scroll_top = self.index
            case Gravity.UP:
                if self.index + 1 == self.scroll_top:
                    self.scroll_top = max(self.scroll_top - 1, 0)
                if self.index + 1 == len(self.lines):
                    self.scroll_top = max((self.index + 1) - max_rows, 0)

    def update_active(self) -> None:
        for i in range(len(self.lines)):
            self.lines[i].is_active = i == self.index

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

    def move_left(self) -> None:
        self.selected_data = self.lines[self.index].data
        if self.state == PageState.CHANNELS:
            self.last_feed_index = self.index
            self.state = PageState.ENTRIES
            if self.selected_data.channel_id == "feed":
                entries = self.feeder.feed()
            else:
                entries = self.feeder.channel_feed(self.selected_data.channel_id)
            self.lines = list(map(Line, entries))
            self.index = 0
            self.scroll_top = 0
        elif self.state == PageState.ENTRIES:
            if not isinstance(self.selected_data, Entry):
                raise Exception(
                    "unexpected selected data type %s: %r"
                    % (type(self.selected_data), self.selected_data)
                )
            play_video(self.selected_data.id)
            exit(0)

    def move_right(self) -> None:
        if self.filtered:
            self.state = PageState.CHANNELS
            self.lines = list(map(Line, self.channels))
            self.filtered = False
            self.index = self.last_feed_index
            self.scroll_top = 0
            return
        if self.state == PageState.CHANNELS:
            exit(0)
        if self.state == PageState.ENTRIES:
            self.state = PageState.CHANNELS
            self.lines = list(map(Line, self.channels))
            self.index = self.last_feed_index
            self.last_feed_index = -1
            self.scroll_top = 0

    def filter_lines(self, sfilter: str) -> None:
        if not sfilter:
            return
        sfilter = sfilter.lower()
        self.lines = list(filter(lambda v: sfilter in v.data.title.lower(), self.lines))
        self.filtered = True

    def handle_slash(self, screen: "curses._CursesWindow") -> None:
        curses.curs_set(1)
        max_y, max_x = screen.getmaxyx()
        n = max_x - 2
        screen.addnstr(max_y - 2, 1, f"{self.status:<{n}}", n, curses.color_pair(Color.ACTIVE))
        screen.move(max_y - 1, 0)
        screen.clrtoeol()
        screen.move(max_y - 1, 2)
        screen.addch("/")
        screen.refresh()
        sfilter = ""
        try:
            while ch := screen.getch():
                screen.refresh()
                max_y, max_x = screen.getmaxyx()
                if ch == 10:
                    if not sfilter:
                        return
                    self.filter_lines(sfilter)
                    return
                if ch in (47, curses.KEY_ENTER, 27):
                    return
                if ch == curses.KEY_BACKSPACE:
                    if not len(sfilter):
                        continue
                    sfilter = sfilter[:len(sfilter) - 1]
                    screen.addnstr(max_y - 1, 3, " " * max_x, max_x - 4)
                    screen.refresh()
                else:
                    sfilter += chr(ch)
                width = min(len(sfilter), max_x - 3)
                screen.addnstr(max_y - 1, 3, sfilter, width or 1)
        except KeyboardInterrupt:
            return
        screen.getkey()

    @property
    def status(self) -> str:
        title = ""
        if self.last_feed_index > -1 and len(self.channels) >= self.last_feed_index + 1:
            title = "%s " % self.channels[self.last_feed_index].title
        return f" {title}[h,j,k,l]: navigate, [gg,K]: top, [G,J]: bottom, [q]: quit"


if __name__ == "__main__":
    config = Config(default_config_path())
    if not config:
        exit(1)
    if not config.storage_path.parent.exists():
        config.storage_path.parent.mkdir(parents=True)

    args = parse_args()
    feeder = Feeder(config, Storage(config.storage_path))

    if is_update_interval_expired():
        print("updating...")
        try:
            asyncio.run(feeder.sync_entries())
        except Exception as e:
            print("Update failed: %s" % e)

    try:
        _ = Picker(feeder, **dict(vars(args))).start()
    except Exception as e:
        print(e)
        exit(1)
