#!/bin/sh

ICON=
LAST_UPDATE_TIMESTAMP=0

DEFAULT_UPDATE_INTERVAL_SEC=$((3600 * 2))
: "${UPDATE_INTERVAL_SEC:=$DEFAULT_UPDATE_INTERVAL_SEC}"
: "${UPDATE_LOCK_PATH:=/tmp/pytfeeder_update.lock}"

: "${PRINT_CHANNELS:=1}"
CHANNELS_FILEPATH="${XDG_CONFIG_HOME:-$HOME/.config}/pytfeeder/channels.yaml"
STORAGE_FILEPATH="${XDG_DATA_DIR:-$HOME/.local/share}/pytfeeder/pytfeeder.db"

notify() { [ -n "$1" ] && notify-send -i youtube -a pytfeeder "$@"; }

channels_with_updates() {
    limit=$1
    case $limit in
    [[:digit:]]*) ;;
    *)
        notify "Invalid number '$limit'"
        exit 0
        ;;
    esac
    channels_list="$(sqlite3 <. -init /dev/null -column "$STORAGE_FILEPATH" \
        "SELECT channel_id FROM tb_entries WHERE channel_id IN (\
        $(yq -r "[.[] | select((.hidden // false) == false) |\
        .channel_id | \"'\"+.+\"'\"] | join(\", \")" "$CHANNELS_FILEPATH"))\
        ORDER BY published DESC LIMIT $limit" |
        awk 'NF { printf "%s .channel_id == \"%s\" ", sep, $0; sep="or" }')"

    if [ -n "$channels_list" ]; then
        yq -r ".[] | select((.hidden // false) == false) |\
            select($channels_list) | .title" "$CHANNELS_FILEPATH" || notify 'yq error'
    fi
}

update() {
    notify 'Start updating...'
    UPDATES="$(pytfeeder -s -H)"
    case $UPDATES in
    0) notify 'No updates' ;;
    0* | *[!0-9]*) notify "Error: $UPDATES" ;;
    [[:digit:]]*)
        if [ $PRINT_CHANNELS -eq 1 ]; then
            channels="$(channels_with_updates $UPDATES)"
            notify "$(printf '%d new updates\n%s' "$UPDATES" "$channels")"
        else
            notify "$UPDATES new updates"
        fi
        ;;
    *) notify "Error: $UPDATES" ;;
    esac
}

case $BLOCK_BUTTON in
1)
    NOW=$(date +%s)
    if [ -f "$UPDATE_LOCK_PATH" ]; then
        LAST_UPDATE_TIMESTAMP=$(cat "$UPDATE_LOCK_PATH")
        [ $((NOW - LAST_UPDATE_TIMESTAMP)) -gt $UPDATE_INTERVAL_SEC ] &&
            update
    else
        UPTIME_SEC=$(uptime -r | cut -d' ' -f2 | cut -d. -f1)
        [ $UPTIME_SEC -gt $UPDATE_INTERVAL_SEC ] && update
    fi
    ;;
2) update ;;
3)
    channels="$(pytfeeder -f '{channels_with_updates}')"
    if [ -n "$channels" ]; then
        notify 'Channels with updates:' "$channels"
    else
        notify 'No updates'
    fi
    ;;
esac

VALUE="$(pytfeeder -f '{unwatched} ({last_update#%H:%M})')"
case $VALUE in
*Unknown*) VALUE="${VALUE%% *}" ;;
esac
[ -n "$ICON" ] && OUTPUT=" $ICON $VALUE " || OUTPUT=" $VALUE "

# underline="underline='single' underline_color='${COLOR3:-#cc241d}'"
printf "<span color='%s' background='%s' weight='bold'>%s</span>\n" \
    "${COLOR1:-#fb4934}" "${COLOR2:-#9d0006}" "$OUTPUT"
