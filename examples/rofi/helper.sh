#!/bin/sh

start_menu(){
    printf "feed\000info\037feed\n"
    pytfeeder-rofi
    printf "\000new-selection\0370\n"
}

printf "\000use-hot-keys\037true\n"

case $ROFI_RETV in
    # channels list on start
    0) start_menu ;;
    # select line
    1)
        case "$ROFI_INFO" in
        feed)
            printf "back\000info\037main\n"
            pytfeeder-rofi -f
            printf "\000new-selection\0370\n"
        ;;
        main) start_menu ;;
        *)
            [ "$(printf '%s' "$ROFI_INFO" |\
                grep -oP "^[0-9a-zA-Z_\-]{24}$")" = "$ROFI_INFO" ] && {
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
        esac
    ;;
    # kb-custom-1 (Ctrl-s) -- sync
    10) 
        [ "$ROFI_DATA" = "main" ] || printf "back\000info\037main\n"
        case $ROFI_DATA in
        feed) pytfeeder-rofi -s -f ;;
        main)  pytfeeder-rofi -s ;;
        *) [ "${#ROFI_DATA}" -eq 24 ] && pytfeeder-rofi -s -i "$ROFI_DATA" ;;
        esac
    ;;
    # kb-custom-2 (Ctrl-c) -- clean cache
    11) pytfeeder-rofi --clean-cache ;;
    # kb-custom-3 (Ctrl-x) -- mark entry as viewed
    12)
        [ "$ROFI_DATA" = "main" ] || printf "back\000info\037main\n"
        case $ROFI_DATA in
        feed) pytfeeder-rofi -v "$ROFI_INFO" -f ;;
        *) [ "${#ROFI_DATA}" -eq 24 ] && pytfeeder-rofi -v "$ROFI_INFO" -i "$ROFI_DATA" ;;
        esac
    ;;
    # kb-custom-4 (Ctrl-a) -- mark current feed entries as viewed
    13)
        [ "$ROFI_DATA" = "main" ] || printf "back\000info\037main\n"
        case $ROFI_DATA in
        feed) pytfeeder-rofi -v all -f ;;
        main) pytfeeder-rofi -v all ;;
        *) [ "${#ROFI_DATA}" -eq 24 ] && pytfeeder-rofi -v "$ROFI_DATA" -i "$ROFI_DATA" ;;
        esac
        printf "\000new-selection\0370"
    ;;
esac
