#!/bin/sh

printf "\000use-hot-keys\037true\n"
main(){
    printf "\000message\037YouTube feeder-rofi\n"
    pytfeeder-rofi
    printf "\000new-selection\0370\n"
}

case $ROFI_RETV in
    # channels list on start
    0) main ;;
    # select line
    1)
        [ "$ROFI_INFO" = "feed" ] && {
            printf "back\000info\037main\n"
            pytfeeder-rofi -f
            printf "\000new-selection\0370\n"
        }
        [ "$ROFI_INFO" = "main" ] && main
        [ "$(printf '%s' "$ROFI_INFO" |\
            grep -oP "^[0-9a-zA-Z_\-]{24}$")" = "$ROFI_INFO" ] && {
            printf "\000message\037%s\n" "$@"
            printf "back\000info\037main\n"
            pytfeeder-rofi -i "$ROFI_INFO"
            printf "\000new-selection\0370\n"
        }
        [ "$(printf '%s' "$ROFI_INFO" |\
            grep -oP "^[0-9a-zA-Z_\-]{11}$")" = "$ROFI_INFO" ] && {
            pytfeeder-rofi -v "$ROFI_INFO" >/dev/null 2>&1
            setsid -f mpv "https://youtu.be/$ROFI_INFO" >/dev/null 2>&1
        }
    ;;
    # kb-custom-1 (Ctrl-s) -- sync
    10) pytfeeder-rofi -s ;;
    # kb-custom-2 (Ctrl-c) -- clean cache
    11) pytfeeder-rofi --clean-cache ;;
    # kb-custom-3 (Ctrl-x) -- mark entry as viewed
    12)
        printf "back\000info\037main\n"
        case $ROFI_DATA in
            common_feed) pytfeeder-rofi -v "$ROFI_INFO" -f ;;
            *) pytfeeder-rofi -v "$ROFI_INFO" -i "$ROFI_DATA" ;;
        esac
    ;;
    # kb-custom-4 (Ctrl-a) -- mark current feed entries as viewed
    13)
        printf "back\000info\037main\n"
        case $ROFI_DATA in
            common_feed) pytfeeder-rofi -v "$ROFI_DATA" -f ;;
            *) pytfeeder-rofi -v "$ROFI_DATA" -i "$ROFI_DATA" ;;
        esac
        printf "\000new-selection\0370"
    ;;
esac
