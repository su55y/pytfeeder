#!/bin/sh

# optional for append
APPEND_SCRIPT="${XDG_DATA_HOME:-$HOME/.local/share}/rofi/playlist_ctl_py/append_video.sh"
# optional for download
DOWNLOAD_DIR="$HOME/Videos/YouTube"
download_vid() {
	[ "${#1}" -eq 11 ] || return
	notify-send -a "pytfeeder" "⬇️Start downloading '$2'..."
	qid="$(tsp yt-dlp "https://youtu.be/$1" -o "$DOWNLOAD_DIR/%(uploader)s/%(title)s.%(ext)s")"
	tsp -D "$qid" notify-send -a "pytfeeder" "✅Download done: '$2'"
}

err_msg() {
	printf '\000message\037error: %s\n' "$1"
	exit 1
}

start_menu() {
	printf "\000markup-rows\037true\n"
	printf "feed\r%s new entries\000info\037feed\n" "$(pytfeeder -u)"
	pytfeeder --rofi --channels-fmt '{title}\r{unviewed_count} new entries\000info\037{id}'
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
		printf "\000markup-rows\037true\n"
		pytfeeder --rofi -f --entries-fmt '{title}\r<b><i>{channel_title}</i></b>\000info\037{id}\037meta\037{meta}'
		printf "\000new-selection\0370\n"
		;;
	main) start_menu ;;
	*)
		if [ "$(printf '%s' "$ROFI_INFO" |
			grep -oP "^[0-9a-zA-Z_\-]{24}$")" = "$ROFI_INFO" ]; then
			printf "back\000info\037main\n"
			pytfeeder --rofi -i="$ROFI_INFO" --entries-fmt '{title}\r<b><i>{updated}</i></b>\000info\037{id}\037meta\037{meta}'
			printf "\000new-selection\0370\n"
		elif [ "$(printf '%s' "$ROFI_INFO" |
			grep -oP "^[0-9a-zA-Z_\-]{11}$")" = "$ROFI_INFO" ]; then
			pytfeeder --rofi -v="$ROFI_INFO" >/dev/null 2>&1
			_play "https://youtu.be/$ROFI_INFO"
		else
			_err_msg "invalid id '$ROFI_INFO'"
		fi
		;;
	esac
	;;
# kb-custom-1 (Ctrl-s) -- sync
10)
	[ "$ROFI_DATA" = "main" ] || printf "back\000info\037main\n"
	case $ROFI_DATA in
	feed) pytfeeder --rofi -s -f ;;
	main)
		printf "feed\000info\037feed\n"
		pytfeeder --rofi -s
		;;
	*)
		[ "${#ROFI_DATA}" -eq 24 ] || err_msg "invalid channel_id '$ROFI_DATA'"
		pytfeeder --rofi -s -i="$ROFI_DATA"
		;;
	esac
	;;
# kb-custom-2 (Ctrl-c) -- clean cache
11) pytfeeder --rofi --clean-cache ;;
# kb-custom-3 (Ctrl-x) -- mark entry as viewed
# kb-custom-6 (Ctrl-d) -- download selected entry
12 | 15)
	[ "$ROFI_DATA" = "main" ] || printf "back\000info\037main\n"
	[ "${#ROFI_INFO}" -eq 11 ] || err_msg "invalid id '$ROFI_INFO'"
	case $ROFI_DATA in
	feed) pytfeeder --rofi -v="$ROFI_INFO" -f ;;
	*)
		[ "${#ROFI_DATA}" -eq 24 ] || err_msg "invalid channel_id '$ROFI_DATA'"
		pytfeeder --rofi -v="$ROFI_INFO" -i="$ROFI_DATA"
		;;
	esac
	[ "$ROFI_RETV" -eq 15 ] && download_vid "$ROFI_INFO" "$1"
	;;
# kb-custom-4 (Ctrl-X) -- mark current feed entries as viewed
13)
	[ "$ROFI_DATA" = "main" ] || printf "back\000info\037main\n"
	case $ROFI_DATA in
	feed) pytfeeder --rofi -v all -f ;;
	main) pytfeeder --rofi -v all ;;
	*)
		[ "${#ROFI_DATA}" -eq 24 ] || err_msg "invalid channel_id '$ROFI_DATA'"
		pytfeeder --rofi -v="$ROFI_DATA" -i="$ROFI_DATA"
		;;
	esac
	printf "\000new-selection\0370"
	;;
# kb-custom-5 (Ctrl-a) -- append selected to playlist
14)
	[ "$ROFI_DATA" = "main" ] || printf "back\000info\037main\n"
	[ -f "$APPEND_SCRIPT" ] || err_msg "append script not found"
	[ "${#ROFI_INFO}" -eq 11 ] || err_msg "invalid id '$ROFI_INFO'"
	setsid -f "$APPEND_SCRIPT" "https://youtu.be/$ROFI_INFO" >/dev/null 2>&1
	case $ROFI_DATA in
	feed) pytfeeder --rofi -v="$ROFI_INFO" -f ;;
	*)
		[ "${#ROFI_DATA}" -eq 24 ] || err_msg "invalid channel_id '$ROFI_DATA'"
		pytfeeder --rofi -v="$ROFI_INFO" -i="$ROFI_DATA"
		;;
	esac
	;;
esac
