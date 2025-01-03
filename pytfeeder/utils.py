import logging
from typing import Dict, Optional

from .models import Channel


def fetch_channel_info(url: str) -> Optional[Channel]:
    try:
        from yt_dlp import YoutubeDL
    except ImportError as e:
        print(f"ImportError: {e!s}")
        return

    with YoutubeDL({"quiet": True}) as ydl:
        info = ydl.extract_info(url, download=False, process=False)
        if not info or not isinstance(info, Dict):
            logging.error(f"Can't extract info by url: {url}")
            return
        title = info.get("title", "Unknown")
        channel_id = info.get("channel_id")
        if not channel_id or len(channel_id) != 24:
            logging.error(f"Invalid channel_id {channel_id!r}\ninfo: {info}")
            return
        return Channel(title=title, channel_id=channel_id)

def human_readable_size(size: int) -> str:
    import math
    if size == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size, 1024)))
    p = math.pow(1024, i)
    s = round(size / p, 2)
    return "%s %s" % (s, size_name[i])
