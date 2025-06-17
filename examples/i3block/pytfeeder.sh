#!/bin/sh

ICON=""
UPDATE_LOCK_PATH=/tmp/pytfeeder_update.lock
UPDATE_INTERVAL_SEC=$((3600 * 2))
LAST_UPDATE_TIMESTAMP=0

notify() {
    [ -n "$1" ] || return
    notify-send -i youtube -a pytfeeder "$@"
}

update() {
    notify "Start updating..."
    UPDATES="$(pytfeeder -s)"
    case $UPDATES in
    0) notify "No updates" ;;
    0* | *[!0-9]*) notify "Error: $UPDATES" ;;
    [[:digit:]]*) notify "$UPDATES new updates" ;;
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
    channels_with_updates="$(pytfeeder -f '{channels_with_updates}')"
    if [ -n "$channels_with_updates" ]; then
        notify 'Channels with updates:' "$channels_with_updates"
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
