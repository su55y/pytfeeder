#!/bin/sh

# optional for append
APPEND_SCRIPT="${XDG_DATA_HOME:-$HOME/.local/share}/rofi/playlist_ctl_py/append_video.sh"
# optional for download
DOWNLOAD_DIR="$HOME/Videos/YouTube"
download_vid() {
	[ "${#1}" -eq 11 ] || return
	title="unknown"
	[ -n "$2" ] && title="$(echo "$2" | sed 's/\r.*//')"
	notify-send -a "pytfeeder" "⬇️Start downloading '$title'..."
	qid="$(tsp yt-dlp "https://youtu.be/$1" -o "$DOWNLOAD_DIR/%(uploader)s/%(title)s.%(ext)s")"
	tsp -D "$qid" notify-send -a "pytfeeder" "✅Download done: '$title'"
}

err_msg() {
	printf '\000message\037error: %s\n' "$1"
	exit 1
}

start_menu() {
	printf "\000markup-rows\037true\n"
	printf "feed\r%s new entries\000info\037feed\n" "$(pytfeeder -u)"
	pytfeeder --rofi --channels-fmt '{title}\r{unviewed_count} new entries\000info\037{id}' "$@"
	printf "\000new-selection\0370\n"
}

print_feed() {
	printf "back\000info\037main\n"
	printf "\000markup-rows\037true\n"
	pytfeeder --rofi -f --entries-fmt '{title}\r<b><i>{channel_title}</i></b>\000info\037{id}\037meta\037{meta}' "$@"
	printf "\000new-selection\0370\n"
}

print_channel_feed() {
	[ -n "$1" ] || return 1
	channel_id="$1"
	shift
	printf "back\000info\037main\n"
	pytfeeder --rofi -i="$channel_id" "$@" --entries-fmt '{title}\r<b>{updated}</b>\000info\037{id}\037meta\037{meta}' --datetime-fmt '<i>%d %B</i>'
}

printf "\000use-hot-keys\037true\n"

case $ROFI_RETV in
# channels list on start
0) start_menu ;;
# select line
1)
	case "$ROFI_INFO" in
	feed) print_feed ;;
	main) start_menu ;;
	*)
		if [ "$(printf '%s' "$ROFI_INFO" |
			grep -oP "^[0-9a-zA-Z_\-]{24}$")" = "$ROFI_INFO" ]; then
			print_channel_feed "$ROFI_INFO"
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
	case $ROFI_DATA in
	feed) print_feed "-s" ;;
	main)
		start_menu "-s"
		;;
	*)
		[ "${#ROFI_DATA}" -eq 24 ] || err_msg "invalid channel_id '$ROFI_DATA'"
		print_channel_feed "$ROFI_DATA" "-s"
		;;
	esac
	;;
# kb-custom-2 (Ctrl-c) -- clean cache
11) pytfeeder --rofi --clean-cache ;;
# kb-custom-3 (Ctrl-x) -- mark entry as viewed
# kb-custom-6 (Ctrl-d) -- download selected entry
12 | 15)
	[ "${#ROFI_INFO}" -eq 11 ] || err_msg "invalid id '$ROFI_INFO'"
	case $ROFI_DATA in
	feed) print_feed "-v=$ROFI_INFO" ;;
	*)
		[ "${#ROFI_DATA}" -eq 24 ] || err_msg "invalid channel_id '$ROFI_DATA'"
		print_channel_feed "$ROFI_DATA" "-v=$ROFI_INFO"
		;;
	esac
	[ "$ROFI_RETV" -eq 15 ] && download_vid "$ROFI_INFO" "$1"
	;;
# kb-custom-4 (Ctrl-X) -- mark current feed entries as viewed
13)
	case $ROFI_DATA in
	feed) print_feed "-v" "all" ;;
	main) start_menu "-v" "all" ;;
	*)
		[ "${#ROFI_DATA}" -eq 24 ] || err_msg "invalid channel_id '$ROFI_DATA'"
		print_channel_feed "$ROFI_DATA" "-v=$ROFI_DATA"
		;;
	esac
	printf "\000new-selection\0370"
	;;
# kb-custom-5 (Ctrl-a) -- append selected to playlist
14)
	[ -f "$APPEND_SCRIPT" ] || err_msg "append script not found"
	[ "${#ROFI_INFO}" -eq 11 ] || err_msg "invalid id '$ROFI_INFO'"
	setsid -f "$APPEND_SCRIPT" "https://youtu.be/$ROFI_INFO" >/dev/null 2>&1
	case $ROFI_DATA in
	feed) print_feed "-v=$ROFI_INFO" ;;
	*)
		[ "${#ROFI_DATA}" -eq 24 ] || err_msg "invalid channel_id '$ROFI_DATA'"
		print_channel_feed "$ROFI_DATA" "-v=$ROFI_INFO"
		;;
	esac
	;;
esac
