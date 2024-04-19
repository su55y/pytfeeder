DEFAULT_LOG_FMT = (
    "[%(asctime)-.19s %(levelname)s] %(message)s (%(filename)s:%(lineno)d)"
)

DEFAULT_CHANNEL_FMT = "{title}\000info\037{id}"
DEFAULT_ENTRY_FMT = "{title}\000info\037{id}\037meta\037{meta}"
DEFAULT_DATETIME_FMT = "%D %T"

YT_FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id=%s"
