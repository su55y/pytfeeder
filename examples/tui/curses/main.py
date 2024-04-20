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
    k = ord("k")
    g = ord("g")
    G = ord("G")
    q = ord("q")
    l = ord("l")
    h = ord("h")
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
    def __init__(self, feeder: Feeder, new_prefix: str = "[+]") -> None:
        self.feeder = feeder
        self.new_prefix = new_prefix

        self.channels = [Channel("Feed", "feed"), *self.feeder.channels]
        self.gravity = Gravity.DOWN
        self.index = 0
        self.last_feed_index = -1
        self.lines = list(map(Line, self.channels))
        self.scroll_top = 0
        self.selected_data = None
        self.state = PageState.CHANNELS

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
            new = isinstance(line.data, Entry) and not line.data.is_viewed
            color_pair = Color.NEW if new else Color.NONE
            new_prefix = " "
            if isinstance(line.data, Entry):
                new_prefix = self.new_prefix if new else " " * len(self.new_prefix)
            text = f"{new_prefix}{line.data.title}"
            if line.is_active:
                text = f"{new_prefix+line.data.title:<{n}}"
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

    def move_down(self) -> None:
        self.gravity = Gravity.DOWN
        self.index = (self.index + 1) % len(self.lines)

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
        if self.state == PageState.CHANNELS:
            exit(0)
        if self.state == PageState.ENTRIES:
            self.state = PageState.CHANNELS
            self.lines = list(map(Line, self.channels))
            self.index = self.last_feed_index
            self.last_feed_index = -1
            self.scroll_top = 0

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
    feeder = Feeder(config, Storage(config.storage_path))
    if is_update_interval_expired():
        print("updating...")
        asyncio.run(feeder.sync_entries())
    try:
        _ = Picker(feeder).start()
    except Exception as e:
        print(e)
        exit(1)
