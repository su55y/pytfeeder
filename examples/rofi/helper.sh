#!/bin/sh

# printf "\000markup-rows\037true\n"
# printf "\000urgent\037true\n"

main(){
    printf "\000message\037YouTube feeder-rofi\n"
    printf "common feed\000info\037feed\n"
    pytfeeder-rofi
    printf "\000new-selection\0370\n"
}

case $ROFI_RETV in
    # channels list on start
    0) main ;;
    # select line
    1)
        notify-send "rofi" "$@"
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
            grep -oP "^[0-9a-zA-Z_\-]{11}$")" = "$ROFI_INFO" ] &&\
            setsid -f mpv "https://youtu.be/$ROFI_INFO" >/dev/null 2>&1
    ;;
esac
