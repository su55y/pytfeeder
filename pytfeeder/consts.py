DEFAULT_LOG_FMT = (
    "[%(asctime)-.19s %(levelname)s] %(message)s (%(filename)s:%(lineno)d)"
)

DEFAULT_CHANNELS_FMT = "{new_mark} | {title}"
DEFAULT_ENTRIES_FMT = "{new_mark} | {updated} | {title}"
DEFAULT_FEED_ENTRIES_FMT = "{new_mark} | {updated} | {channel_title} | {title}"
DEFAULT_ROFI_CHANNELS_FMT = "{title}\000info\037{id}"
DEFAULT_ROFI_ENTRIES_FMT = "{title}\000info\037{id}\037meta\037{meta}"
DEFAULT_DATETIME_FMT = "%D %T"

YT_FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id=%s"
