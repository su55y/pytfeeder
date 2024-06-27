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
DEFAULT_STATUS_FMT = " {index}{title}{keybinds}"
DEFAULT_DATETIME_FMT = "%b %d"
OPTIONS_DESCRIPTION = """
channels-fmt keys:
    {new_mark} - new-mark if have updates, otherwise `' '*len(new_mark)`
    {title}    - title of the channel
entries-fmt keys:
    {new_mark}      - new-mark if have updates, otherwise `' '*len(new_mark)`
    {title}         - title of the entry
    {updated}       - updated in `--datetime-fmt` format (rss `updated` value or fetch date)
    {channel_title} - title of the channel
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        epilog=OPTIONS_DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
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
    parser.add_argument(
        "--status-fmt",
        default=DEFAULT_STATUS_FMT,
        metavar="STR",
        help="status bar format (default: %(default)r)",
    )
    parser.add_argument(
        "--datetime-fmt",
        default=DEFAULT_DATETIME_FMT,
        metavar="STR",
        help="`{updated}` datetime format of entry (default: %(default)r)",
    )
    parser.add_argument(
        "--hide-feed", action="store_true", help="Hide 'Feed' in channels list"
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
    a = ord("a")
    A = ord("A")
    p = ord("p")
    n = ord("n")
    TAB = 9
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
        status_fmt: str = DEFAULT_STATUS_FMT,
        datetime_fmt: str = DEFAULT_DATETIME_FMT,
        hide_feed: bool = False,
    ) -> None:
        self.feeder = feeder

        if hide_feed:
            self.channels = self.feeder.channels
        else:
            feed_channel = Channel(
                title="Feed",
                channel_id="feed",
                have_updates=bool(self.feeder.unviewed_count()),
            )
            self.channels = [feed_channel, *self.feeder.channels]

        self.channels_fmt = channels_fmt
        self.entries_fmt = entries_fmt
        self.status_fmt = status_fmt
        self.datetime_fmt = datetime_fmt
        self.filtered = False
        self.gravity = Gravity.DOWN
        self.index = 0
        self.last_channel_index = -1
        self.last_feed_index = -1
        self.lines = list(map(Line, self.channels))
        self.max_len_chan_title = max(len(c.title) for c in self.channels)
        self.new_mark = new_mark
        self.scroll_top = 0
        self.selected_data = None
        self.state = PageState.CHANNELS
        self._g_pressed = False

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
            match screen.getch():
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
                    screen.clear()
                    self.move_left()
                case Key.K | curses.KEY_HOME:
                    self.move_top()
                case Key.g:
                    if self._g_pressed:
                        self.move_top()
                    self._g_pressed = not self._g_pressed
                case Key.G | Key.J | curses.KEY_END:
                    self.move_bottom()
                case Key.SLASH:
                    self.handle_slash(screen)
                case Key.a:
                    self.mark_viewed()
                case Key.A:
                    self.mark_viewed_all()
                case Key.q:
                    exit(0)

    def draw(self, screen: "curses._CursesWindow") -> None:
        x, y = 0, 0
        max_y, max_x = screen.getmaxyx()
        max_rows = max_y - y - 1
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
                updated = line.data.updated.strftime(self.datetime_fmt)
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
                text = self.channels_fmt.format(
                    new_mark=new_mark, title=line.data.title
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

    def move_right(self, last_channel_index: int = -1) -> None:
        if last_channel_index > -1:
            self.selected_data = self.channels[last_channel_index]
        else:
            self.selected_data = self.lines[self.index].data

        if self.state == PageState.CHANNELS:
            self.state = PageState.ENTRIES
            if last_channel_index == -1:
                self.last_feed_index = self.index
            if self.selected_data.channel_id == "feed":
                entries = self.feeder.feed()
            else:
                entries = self.feeder.channel_feed(self.selected_data.channel_id)
            self.lines = list(map(Line, entries))
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
            exit(0)

    def move_left(self) -> None:
        if self.state == PageState.CHANNELS:
            if not self.filtered:
                exit(0)
            self.lines = list(map(Line, self.channels))
            self.index = min(self.last_feed_index, len(self.lines) - 1)
            self.last_feed_index = -1
            self.scroll_top = 0
        elif self.state == PageState.ENTRIES:
            self.state = PageState.CHANNELS
            if not self.filtered:
                self.lines = list(map(Line, self.channels))
                self.index = min(self.last_feed_index, len(self.lines) - 1)
                self.last_feed_index = -1
                self.scroll_top = 0
            else:
                self.move_right(self.last_channel_index)
                self.last_channel_index = self.last_feed_index
        if self.filtered:
            self.filtered = False

    def filter_lines(self, keyword: str) -> None:
        if not keyword:
            return
        keyword = keyword.lower()
        self.lines = list(filter(lambda v: keyword in v.data.title.lower(), self.lines))
        self.index = 0
        self.scroll_top = 0
        self.gravity = Gravity.DOWN
        self.filtered = True
        curses.curs_set(0)

    def handle_slash(self, screen: "curses._CursesWindow") -> None:
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
        screen.addch("/")
        screen.refresh()
        keyword = ""
        try:
            while ch := screen.getch():
                screen.refresh()
                max_y, max_x = screen.getmaxyx()
                if ch == 10:
                    if not keyword:
                        return
                    screen.clear()
                    self.filter_lines(keyword)
                    return
                if ch in (Key.SLASH, Key.ESC):
                    screen.refresh()
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
            self.feeder.mark_as_viewed()
            for i in range(len(self.channels)):
                self.channels[i].have_updates = False
        elif self.state == PageState.ENTRIES and isinstance(self.selected_data, Entry):
            if self.channels[self.last_feed_index].channel_id == "feed":
                self.feeder.mark_as_viewed()
                for i in range(len(self.channels)):
                    self.channels[i].have_updates = False
                for i in range(len(self.lines)):
                    self.lines[i].data.is_viewed = True  # type: ignore
            else:
                self.feeder.mark_as_viewed(channel_id=self.selected_data.channel_id)
                self.channels[self.last_feed_index].have_updates = False
                for i in range(len(self.lines)):
                    self.lines[i].data.is_viewed = True  # type: ignore

    def mark_viewed(self) -> None:
        self.selected_data = self.lines[self.index].data
        if self.state == PageState.CHANNELS and isinstance(self.selected_data, Channel):
            if self.selected_data.channel_id == "feed":
                return
            self.feeder.mark_as_viewed(channel_id=self.selected_data.channel_id)
            self.selected_data.have_updates = False
        elif self.state == PageState.ENTRIES and isinstance(self.selected_data, Entry):
            self.feeder.mark_as_viewed(id=self.selected_data.id)
            self.selected_data.is_viewed = True

    @property
    def status(self) -> str:
        return self._format_status()

    def _format_status(self) -> str:
        title = ""
        if self.last_feed_index > -1 and len(self.channels) >= self.last_feed_index + 1:
            title = "%s " % self.channels[self.last_feed_index].title
        if self.filtered:
            title = "%d found " % len(self.lines)
        return self.status_fmt.format(
            index=self._status_index, title=title, keybinds=self._status_keybinds
        )

    @property
    def _status_keybinds(self) -> str:
        keybinds_str = "[h,j,k,l]: navigate, [gg,K]: top, [G,J]: bottom, [q]: quit, [a]: mark viewed, [A]: mark viewed all"
        if self.filtered:
            keybinds_str = f"[h]: cancel filter, {keybinds_str}"
        return keybinds_str

    @property
    def _status_index(self) -> str:
        num_fmt = f"%{len(str(len(self.lines)))}d"
        return "[%s/%s] " % ((num_fmt % (self.index + 1)), (num_fmt % len(self.lines)))


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
