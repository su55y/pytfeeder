DEFAULT_CHANNELS_FMT = "{index} {new_mark} {unwatched_total} {title}"
DEFAULT_DATETIME_FMT = "%b %d"
DEFAULT_ENTRIES_FMT = "{index} {new_mark} {published} {title}"
DEFAULT_FEED_ENTRIES_FMT = "{index} {new_mark} {published} {channel_title} {title}"
DEFAULT_LAST_UPDATE_FMT = "%D %T"
DEFAULT_NEW_MARK = "N"
DEFAULT_STATUS_FMT = "{msg} {index} {title} {keybinds}"
DEFAULT_UPDATE_INTERVAL_MINS = 30
DEFAULT_KEYBINDS = "[h,j,k,l]: navigate, [q]: quit, [?]: help"
DEFAULT_DOWNLOAD_OUTPUT = "~/Videos/YouTube/%(uploader)s/%(title)s.%(ext)s"

OPTIONS_DESCRIPTION = """
macros available only in entries screens.
macros args:
    $1 - id
    $2 - title

channels-fmt keys:
    {index}           - line index
    {title}           - title of the channel
    {new_mark}        - show mark if have updates, otherwise `' '*len(new_mark)`
    {unwatched}       - count of unwatched entries
    {total}           - total entries count except deleted
    {unwatched_total} - '({unwatched}/{total})' string aligned to right

entries-fmt keys:
    {index}         - line index
    {new_mark}      - show mark if unwatched, otherwise `' '*len(new_mark)`
    {title}         - title of the entry
    {published}     - publication date (uses `--datetime-fmt`)
    {channel_title} - title of the channel

status-fmt keys:
    {index}         - current line index
    {msg}           - status message
    {title}         - current feed title
    {last_update}   - time of last update (optionally formatted with `--last-update-fmt`)
"""

HELP_KEYBINDINGS = [
    ("h, Left", "Return to previous screen/Quit"),
    ("j, Down, Tab, n", "Move to the next entry"),
    ("k, Up, S-Tab, p", "Move to the previous entry"),
    ("l, Right, Enter", "Open feed/entry"),
    ("gg, Home", "Move to the top of list"),
    ("G, End", "Move to the bottom of list"),
    ("J", "Move to the next feed"),
    ("K", "Move to the prev feed"),
    ("a", "Mark entry/feed as watched"),
    ("A", "Mark all entries/feeds as watched"),
    ("r", "Reload/sync feeds"),
    ("d", "Download video"),
    ("D", "Download all unwatched from current page"),
    ("C-x, Del", "Mark entry as delete"),
    ("C-d", "Mark all entries as deleted"),
    ("/", "Open filter"),
    ("s", "Toggle statusbar visability"),
    ("t", "Toggle empty channels visability"),
    ("u", "Toggle unwatched_first setting"),
    ("h", "Cancel filter"),
    ("c", "Clear screen"),
    ("0-9", "Jump to line {index}"),
    ("F1-F4", "Execute macro 1-4"),
    ("q", "Quit"),
]
