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
    ("q, C-c", "Quit"),
    ("h, Left, q, Backspace", "Return to previous screen/Quit"),
    ("j, Down", "Move to next entry"),
    ("k, Up", "Move to previous entry"),
    ("l, o, Right, Enter, Space", "Open selected feed/entry"),
    ("n", "Move to next unwatched entry"),
    ("p", "Move to previous unwatched entry"),
    ("b, PageUp", "Move to previous page"),
    ("f, PageDown", "Move to next page"),
    ("gg, Home", "Move to top of the list"),
    ("G, End", "Move to bottom of the list"),
    ("0-9", "Jump to line {index}"),
    ("J", "Move to next feed"),
    ("K", "Move to previous feed"),
    ("a", "Mark entry/feed as watched"),
    ("A", "Mark all entries/feeds as watched"),
    ("r", "Reload/sync feeds"),
    ("d", "Download entry"),
    ("D", "Download all unwatched from current feed"),
    ("C-x, Del", "Mark entry as deleted"),
    ("C-d", "Mark all entries as deleted"),
    ("C-r", "Enter channels restoring"),
    ("C-o", "Open channel in browser"),
    ("Enter, Space", "Restore whole channel in restore mode"),
    ("l, o, Right", "Enter channel in restore mode"),
    ("/", "Open filter prompt (C-c or Esc to close)"),
    ("h", "Cancel filter"),
    ("s", "Toggle statusbar visability"),
    ("t", "Toggle empty channels visability"),
    ("u", "Toggle unwatched_first setting"),
    ("Tab", "Open tags"),
    ("c", "Redraw screen"),
    ("F1-F4", "Execute macro 1-4"),
]
