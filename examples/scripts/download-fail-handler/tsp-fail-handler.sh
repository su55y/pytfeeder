#!/bin/sh

[ $# -eq 4 ] || exit 0

LOG_FILE=/tmp/tsp_fail_handler.log
FAILED_JOBS_HISTORY=/tmp/tsp_failed_jobs_history.log
MAX_RETRIES=3

jobid="$1"
error="$2"
outfile="$3"
cmd="$4"

[ "$error" -eq 0 ] && exit 0

# verify that job has label 'pytfeeder'
pattern="^$jobid\s+(running|finished)\s+[^\s]+\s+\[pytfeeder\]\K(yt-dlp.+)$"
[ "$(tsp -l | grep -oP "$pattern")" = "$cmd" ] || exit 0

trynum="$(grep -cx "$cmd" $FAILED_JOBS_HISTORY)"
if [ $trynum -gt $MAX_RETRIES ]; then
    exit 0
elif [ $trynum = $MAX_RETRIES ]; then
    printf "%s [%s] Giving up on '%s' after %s retries" \
        "$(date +%T)" "$jobid" "$cmd" "$trynum" >>$LOG_FILE
    exit 0
fi

echo "$cmd" >>$FAILED_JOBS_HISTORY

printf '%s Handling fail\n -- jobid: %s\n -- error: %s\n -- outfile: %s\n -- cmd: %s\n' \
    "$(date +%T)" "$jobid" "$error" "$outfile" "$cmd" >>$LOG_FILE

notify-send -a tsp-fail-handler "Enqueuing back ($((trynum + 1))) '$cmd'..."
notify_cmd="$(tsp -l | grep -oP "^\d+\s+queued\s+\(file\)\s+\[$jobid\]&&\s\K(.+)$")"
new_jobid="$(tsp $cmd)"
if [ -n "$notify_cmd" ]; then
    set -- $notify_cmd
    shift
    while [ "${1#-}" != "$1" ]; do shift 2; done
    body="$*"
    tsp -D "$new_jobid" notify-send -a tsp-fail-handler "$body"
fi

printf '%s [%s] Retry (%s) tsp %s\n' "$(date +%T)" \
    "$new_jobid" "$((trynum + 1))" "$cmd" >>$LOG_FILE
