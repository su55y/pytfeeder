#!/bin/sh

# optional for download
DOWNLOAD_OUTPUT="$HOME/Videos/YouTube/%(uploader)s/%(title)s.%(ext)s"
# go helper executable
PYTFEEDER_GO_ROFI="$SCRIPTPATH/go-ytfeeder-rofi"
# storage filepath
PYTFEEDER_STORAGE="${XDG_DATA_HOME:-$HOME/.local/share}/pytfeeder/pytfeeder.db"

notify() { [ -n "$1" ] && notify-send -a pytfeeder "$1"; }

err_msg() {
    [ -n "$1" ] && printf '\000message\037error: %s\n\000urgent\0370\n \000nonselectable\037true\n' "$1"
    exit 1
}

[ -f "$PYTFEEDER_GO_ROFI" ] || err_msg "go executable not found at $PYTFEEDER_GO_ROFI"

clean_title() {
    echo "$1" | sed -E 's/<[^>]+>[^<]*<\/[^>]*>//g' | sed 's/\r.*//;s/^[ \t]*//;s/[ \t]*$//'
}

download_vid() {
    [ "${#1}" -eq 11 ] || return
    title="$(clean_title "$2")"
    notify "⬇️Start downloading '$title'..."
    qid="$(tsp -L pytfeeder yt-dlp "https://youtu.be/$1" -o "$DOWNLOAD_OUTPUT")"
    tsp -D "$qid" notify-send -a pytfeeder "✅Download done: '$title'"
}

play() {
    title="$(clean_title "$2")"
    notify "Playing '$title'..."
    setsid -f mpv "$1" >/dev/null 2>&1
}

mark_as_watched() {
    [ -f "$PYTFEEDER_STORAGE" ] || err_msg "$PYTFEEDER_STORAGE not found"
    [ "${#1}" -eq 11 ] || err_msg "invalid id '$1' (${#1})"
    value=1
    [ "$2" = toggle ] && value='NOT is_viewed'
    err="$(sqlite3 "$PYTFEEDER_STORAGE" \
        "UPDATE tb_entries SET is_viewed = $value WHERE id = '$1'")"
    [ -n "$err" ] && err_msg "$err"
}

# shellcheck disable=SC2059
mark_channel_as_watched() {
    [ -f "$PYTFEEDER_STORAGE" ] || err_msg "$PYTFEEDER_STORAGE not found"
    [ "${#1}" -eq 24 ] || err_msg "invalid channel_id '$1' (${#1})"
    q="UPDATE tb_entries SET is_viewed = CASE WHEN EXISTS ( \
        SELECT 1 FROM tb_entries \
        WHERE channel_id = '$1' AND is_deleted = 0 AND is_viewed = 0 \
    ) THEN 1 ELSE 0 END \
    WHERE channel_id = '$1' and is_deleted = 0"
    err="$(sqlite3 "$PYTFEEDER_STORAGE" "$q")"
    [ -n "$err" ] && err_msg "$err"
}

print_feed() {
    printf '\000keep-filter\037true\n'
    printf '\000keep-selection\037true\n'
    printf 'back\000info\037main\n'
    "$PYTFEEDER_GO_ROFI" -i feed \
        -feed-entries-fmt '{title}\r<b>{published}</b> <i>{channel_title}</i>\000info\037{id}\037active\037{active}' \
        -datetime-fmt '<i>%d %B</i>'
}

start_menu() {
    case "$N" in
    2) print_feed ;;
    *)
        "$PYTFEEDER_GO_ROFI" -channels-fmt '<b>[{unwatched_total}]</b> {title}\000info\037{id}\037active\037{active}'
        printf "\000new-selection\0370\n"
        ;;
    esac
}

print_channel_feed() {
    [ "${#1}" -eq 24 ] || err_msg "invalid channel_id '$1'"
    printf '\000keep-filter\037true\n'
    printf '\000keep-selection\037true\n'
    printf 'back\000info\037main\n'
    "$PYTFEEDER_GO_ROFI" -i="$1" \
        -entries-fmt '<b>{published}</b> {title}\000info\037{id}\037active\037{active}' \
        -datetime-fmt '%b %d'
}

printf '\000markup-rows\037true\n'
printf '\000use-hot-keys\037true\n'

case $ROFI_RETV in
# channels list on start
0) start_menu ;;
# select line
1)
    case "$ROFI_INFO" in
    feed) setsid -f "${SCRIPTPATH}/launcher.sh" 2 >/dev/null 2>&1 ;;
    main)
        case $N in
        2) setsid -f "${SCRIPTPATH}/launcher.sh" >/dev/null 2>&1 ;;
        *) start_menu ;;
        esac
        ;;
    *)
        if echo "$ROFI_INFO" | grep -sP '^[-_0-9a-zA-Z]{24}$' >/dev/null 2>&1; then
            print_channel_feed "$ROFI_INFO"
            printf "\000new-selection\0370\n"
        elif echo "$ROFI_INFO" | grep -sP '^[-_0-9a-zA-Z]{11}$' >/dev/null 2>&1; then
            mark_as_watched "$ROFI_INFO"
            play "https://youtu.be/$ROFI_INFO" "$@"
        else
            err_msg "invalid id '$ROFI_INFO'"
        fi
        ;;
    esac
    ;;
# kb-custom-1 (Ctrl-s) -- sync
10)
    new_entries="$(pytfeeder -s)"
    pritnf '\000message\037%s new entries\n' "$new_entries" # FIXME ???
    case $ROFI_DATA in
    feed) print_feed ;;
    main) start_menu ;;
    *) print_channel_feed "$ROFI_DATA" ;;
    esac
    ;;
# kb-custom-2 (Ctrl-x) -- mark entry as viewed
# kb-custom-5 (Ctrl-d) -- download selected entry
11 | 14)
    toggle=
    [ "$ROFI_RETV" -eq 11 ] && toggle=toggle
    mark_as_watched "$ROFI_INFO" "$toggle"

    case $ROFI_DATA in
    feed) print_feed ;;
    *) print_channel_feed "$ROFI_DATA" ;;
    esac
    if [ "$ROFI_RETV" -eq 14 ]; then
        download_vid "$ROFI_INFO" "$1" >/dev/null 2>&1
    fi
    ;;
# kb-custom-3 (Ctrl-X) -- mark current feed entries as viewed
12)
    mark_channel_as_watched "$ROFI_DATA"
    case $ROFI_DATA in
    feed) print_feed ;;
    main) start_menu ;;
    *) print_channel_feed "$ROFI_DATA" ;;
    esac
    ;;
esac
