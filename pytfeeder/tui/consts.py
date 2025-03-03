DEFAULT_CHANNELS_FMT = "{new_mark} | {title}"
DEFAULT_DATETIME_FMT = "%D %T"
DEFAULT_ENTRIES_FMT = "{new_mark} | {updated} | {title}"
DEFAULT_FEED_ENTRIES_FMT = "{new_mark} | {updated} | {channel_title} | {title}"
DEFAULT_LAST_UPDATE_FMT = "%D %T"
DEFAULT_NEW_MARK = "[+]"
DEFAULT_STATUS_FMT = "{msg}{index} {title} {keybinds}"
DEFAULT_UPDATE_INTERVAL_MINS = 30
DEFAULT_KEYBINDS = "[h,j,k,l]: navigate, [q]: quit, [?]: help"
DEFAULT_LOCK_FILE = "/tmp/pytfeeder_update.lock"

OPTIONS_DESCRIPTION = """
macros available only in entries screens.
macros args:
    $1 - id
    $2 - title

channels-fmt keys:
    {index}           - line index
    {new_mark}        - show mark if have updates, otherwise `' '*len(new_mark)`
    {title}           - title of the channel
    {unwatched_count} - count of unwatched entries

entries-fmt keys:
    {index}         - line index
    {new_mark}      - show mark if unwatched, otherwise `' '*len(new_mark)`
    {title}         - title of the entry
    {updated}       - updated in `--datetime-fmt` format (rss `updated` value or fetch date)
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
    ("A", "Mark all enties/feeds as watched"),
    ("r", "Reload/sync feeds"),
    ("d", "Download video"),
    ("D", "Download all NEW (from current page)"),
    ("/", "Open filter"),
    ("h", "Cancel filter"),
    ("c", "Clear screen"),
    ("0-9", "Jump to line {index}"),
    ("F1-F4", "Execute macro 1-4"),
    ("q", "Quit"),
]
