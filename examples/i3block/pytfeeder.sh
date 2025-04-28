#!/bin/sh

ICON=""

update() {
    updates="$(pytfeeder -s)"
    case $updates in
    0) notify-send -a pytfeeder "No updates" ;;
    *) notify-send -a pytfeeder "$updates new updates" ;;
    esac
}

case $BLOCK_BUTTON in
1) update ;;
esac

VALUE="$(pytfeeder -u)"
[ -n "$ICON" ] && OUTPUT=" $ICON $VALUE " || OUTPUT=" $VALUE "

# underline="underline='single' underline_color='${COLOR3:-#cc241d}'"
printf "<span color='%s' background='%s' weight='bold'>%s</span>\n" \
    "${COLOR1:-#fb4934}" "${COLOR2:-#9d0006}" "$OUTPUT"
