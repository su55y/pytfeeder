#!/bin/sh

# optional for append
APPEND_SCRIPT="${XDG_DATA_HOME:-$HOME/.local/share}/rofi/playlist_ctl_py/append_video.sh"
# optional for download
DOWNLOAD_OUTPUT="$HOME/Videos/YouTube/%(uploader)s/%(title)s.%(ext)s"

notify() { [ -n "$1" ] && notify-send -a pytfeeder "$1"; }

err_msg() {
    [ -n "$1" ] && printf '\000message\037error: %s\n\000urgent\0370\n \000nonselectable\037true\n' "$1"
    exit 1
}

clean_title() {
    echo "$1" | sed -E 's/<[^>]+>[^<]*<\/[^>]*>//g' | sed 's/\r.*//;s/^[ \t]*//;s/[ \t]*$//'
}

download_vid() {
    [ "${#1}" -eq 11 ] || return
    title="$(clean_title "$2")"
    notify "⬇️Start downloading '$title'..."
    qid="$(tsp yt-dlp "https://youtu.be/$1" -o "$DOWNLOAD_OUTPUT")"
    tsp -D "$qid" notify-send -a pytfeeder "✅Download done: '$title'"
}

play() {
    title=$(clean_title "$2")
    notify "Playing '$title'..."
    setsid -f mpv "$1" >/dev/null 2>&1
}

start_menu() {
    pytfeeder-rofi "$@" \
        --channels-fmt '{title}\r<i><b>{unwatched}</b> new entries</i>\000info\037{id}\037active\037{active}'
    printf '\000new-selection\0370\n'
}

print_feed() {
    printf 'back\000info\037main\n'
    pytfeeder-rofi "$@" -f \
        --feed-entries-fmt '{title}\r<b><i>{channel_title}</i></b> {published}\000info\037{id}\037meta\037{meta}\037active\037{active}' \
        --datetime-fmt '<i>%d %B</i>'
}

print_channel_feed() {
    [ "${#1}" -eq 24 ] || err_msg "invalid channel_id '$1'"
    channel_id="$1"
    shift
    printf 'back\000info\037main\n'
    pytfeeder-rofi "$@" -i="$channel_id" \
        --entries-fmt '{title}\r<b>{published}</b>\000info\037{id}\037meta\037{meta}\037active\037{active}' \
        --datetime-fmt '<i>%d %B</i>'
}

print_tags() {
    printf 'back\000info\037main\n'
    pytfeeder-rofi --tags \
        --channels-fmt '{title}\r<i><b>{unwatched}</b> new entries</i>\000info\037{id}\037active\037{active}'
}

printf '\000use-hot-keys\037true\n'
printf '\000markup-rows\037true\n'

case $ROFI_RETV in
# channels list on start
0) start_menu ;;
# select line
1)
    case "$ROFI_INFO" in
    feed)
        print_feed
        printf '\000new-selection\0370\n'
        ;;
    main) start_menu ;;
    tags) print_tags ;;
    *)
        if [ "$ROFI_DATA" = tags ]; then
            printf 'back\000info\037tags\n'
            pytfeeder-rofi --tag "$ROFI_INFO" \
                --channels-fmt '{title}\r<i><b>{unwatched}</b> new entries</i>\000info\037{id}\037active\037{active}'
        elif echo "$ROFI_INFO" | grep -sP '^[-_0-9a-zA-Z]{24}$' >/dev/null 2>&1; then
            print_channel_feed "$ROFI_INFO"
            printf '\000new-selection\0370\n'
        elif echo "$ROFI_INFO" | grep -sP '^[-_0-9a-zA-Z]{11}$' >/dev/null 2>&1; then
            pytfeeder-rofi -w="$ROFI_INFO" >/dev/null 2>&1
            play "https://youtu.be/$ROFI_INFO" "$1"
        else
            err_msg "invalid id '$ROFI_INFO'"
        fi
        ;;
    esac
    ;;
# kb-custom-1 (Ctrl-s) -- sync
10)
    case $ROFI_DATA in
    feed) print_feed "-s" ;;
    main) start_menu "-s" ;;
    *) print_channel_feed "$ROFI_DATA" "-s" ;;
    esac
    ;;
# kb-custom-2 (Ctrl-x) -- mark entry as viewed
# kb-custom-5 (Ctrl-d) -- download selected entry
11 | 14)
    [ "${#ROFI_INFO}" -eq 11 ] || err_msg "invalid id '$ROFI_INFO'"
    case $ROFI_DATA in
    feed) print_feed "-w=$ROFI_INFO" ;;
    *) print_channel_feed "$ROFI_DATA" "-w=$ROFI_INFO" ;;
    esac
    [ "$ROFI_RETV" -eq 14 ] && download_vid "$ROFI_INFO" "$1" >/dev/null 2>&1
    ;;
# kb-custom-3 (Ctrl-X) -- mark current feed entries as viewed
12)
    case $ROFI_DATA in
    feed) print_feed "-w" "all" ;;
    main) start_menu "-w" "all" ;;
    *) print_channel_feed "$ROFI_DATA" "-w=$ROFI_DATA" ;;
    esac
    printf '\000new-selection\0370'
    ;;
# kb-custom-4 (Ctrl-a) -- append selected to playlist
13)
    [ -f "$APPEND_SCRIPT" ] || err_msg "append script not found"
    [ "${#ROFI_INFO}" -eq 11 ] || err_msg "invalid id '$ROFI_INFO'"
    setsid -f "$APPEND_SCRIPT" "https://youtu.be/$ROFI_INFO" >/dev/null 2>&1
    case $ROFI_DATA in
    feed) print_feed "-w=$ROFI_INFO" ;;
    *) print_channel_feed "$ROFI_DATA" "-w=$ROFI_INFO" ;;
    esac
    ;;
# kb-custom-6 (Ctrl+Tab) -- show tags
15) print_tags ;;
esac
