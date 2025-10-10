#!/usr/bin/env bash

PYTFEEDER_CHANNELS_PATH="${XDG_CONFIG_HOME:-$HOME/.config}/pytfeeder/channels.yaml"
PYTFEEDER_DB_PATH="${XDG_DATA_HOME:-$HOME/.local/share}/pytfeeder/pytfeeder.db"
DOWNLOAD_OUTPUT="$HOME/Videos/YouTube/%(uploader)s/%(title)s.%(ext)s"
FEED_LIMIT=100

if [ ! -f "$PYTFEEDER_CHANNELS_PATH" ]; then
    echo "config file $PYTFEEDER_CHANNELS_PATH not found"
    exit 1
fi

if [ ! -f "$PYTFEEDER_DB_PATH" ]; then
    echo "db file $PYTFEEDER_DB_PATH not found"
    exit 1
fi

declare -A all_channels_map
declare -A channels_map
ids_string=
while IFS=' ' read -r id title; do
    all_channels_map[$id]="$title"
    if [ -z "$ids_string" ]; then
        ids_string="'$id'"
    else
        ids_string="$ids_string, '$id'"
    fi
done < <(yq -r '.[] | select((.hidden // false) == false) | .channel_id+" "+.title' \
    "$PYTFEEDER_CHANNELS_PATH")

while read -r id; do
    channels_map[$id]="${all_channels_map[$id]}"
done < <(
    sqlite3 <. -init /dev/null -column "$PYTFEEDER_DB_PATH" "\
    SELECT channel_id FROM tb_entries \
    WHERE is_deleted = 0 and channel_id IN ($ids_string) \
    GROUP BY channel_id"
)

select_query() {
    if [ "$1" = feed ]; then
        cat <<EOF
        SELECT id, is_viewed, title, channel_id FROM tb_entries
        WHERE  is_deleted = 0
        AND channel_id IN ($(
            yq -r '[.[] | select((.hidden // false) == false) |
            ("'\''" + (.channel_id|tostring) + "'\''")] | join(", ")' \
                "$PYTFEEDER_CHANNELS_PATH"
        ))
        ORDER BY published DESC
        LIMIT $FEED_LIMIT
EOF
    else
        cat <<EOF
        SELECT id, is_viewed, title FROM tb_entries
        WHERE is_deleted = 0 AND channel_id = '${1}'
        ORDER BY published DESC
EOF
    fi
}

print_channels() {
    echo 'feed Feed'
    for k in "${!channels_map[@]}"; do
        echo "$k ${channels_map[$k]}"
    done
}

# shellcheck disable=SC2016,SC2059
while :; do
    channel_line="$(print_channels | fzf --with-nth 2.. --preview='')"
    [ -n "$channel_line" ] || exit 0
    channel_id="${channel_line%% *}"
    channel_title="${channel_line#* }"

    selected_line="$(
        echo __go_back__ |
            sqlite3 <. -init /dev/null -column "$PYTFEEDER_DB_PATH" \
                "$(select_query "$channel_id")" |
            while read -r line; do
                line=$(echo "$line" | tr -s ' ')
                id="${line%% *}"
                is_viewed="$(echo "$line" | cut -d' ' -f 2)"
                title="$(echo "$line" | cut -d' ' -f 3-)"
                if [ "$channel_id" = feed ]; then
                    cid="${title##* }"
                    title="${title% *}"
                    c_title="${channels_map[$cid]}"
                    id="$(printf '%s \033[3m%s\033[0m' "$id" "$c_title")"
                fi
                if [ $is_viewed -eq 0 ]; then
                    printf '%s \033[1;32m%s\033[0m\n' "$id" "$title"
                else
                    echo "$id $title"
                fi
            done | fzf --ansi --ghost="$channel_title" \
            --header='[esc,ctrl-q]: Go back, [ctrl-space]: Play' \
            --bind='ctrl-space:execute-silent(\
    notify-send -i youtube -a pytfeeder "Playing \"$(echo {} |\
    sed "s/^[-_0-9a-zA-Z]\{11\}[ \t]*//;s/[[ \t]*$//")\"..." &&\
    setsid -f mpv "https://youtu.be/$(echo {} | cut -d" " -f1)" >/dev/null 2>&1)' \
            --with-nth 2.. --preview=''
    )"

    [ -n "$selected_line" ] || continue

    vid_id="${selected_line%% *}"
    vid_title="$(echo "${selected_line#* }" | sed 's/^[ \t]*//; s/[ \t\n]*$//')"

    [ -n "$vid_id" ] || exit 0
    notify-send -i youtube -a pytfeeder "⬇️Start downloading '$vid_title'..."
    qid="$(tsp -L pytfeeder yt-dlp "https://youtu.be/$vid_id" -o "$DOWNLOAD_OUTPUT")"
    tsp -D "$qid" notify-send -i youtube -a pytfeeder "✅Download done: '$vid_title'" >/dev/null 2>&1
done
