import logging
from os.path import expandvars
from pathlib import Path
import re
from urllib.request import urlopen
from urllib.parse import urlparse
from xml.etree.ElementTree import XML


from .models import Channel


def expand_path(path: Path) -> Path:
    return Path(expandvars(path)).expanduser()


def fetch_channel_info(url: str) -> Channel:
    return _try_fetch_channel_info(url) or _fetch_channel_info_fallback(url)


def _parse_channel_info(
    raw: str, cid: str | None, username: str | None
) -> Channel | None:
    t = XML(raw)
    title = t.findtext("{http://www.w3.org/2005/Atom}title") or username
    channel_id = t.findtext(
        "yt:channelId",
        namespaces={"yt": "http://www.youtube.com/xml/schemas/2015"},
    )
    if channel_id:
        channel_id = f"UC{channel_id}"
    else:
        channel_id = cid
    if not title or not channel_id:
        return None
    return Channel(channel_id=channel_id, title=title)


def _try_fetch_channel_info(url: str) -> Channel | None:
    u = urlparse(url)
    feed_url = ""
    cid = username = None
    if m := re.match(r"/channel/(UC[-_0-9a-zA-Z]{22})", u.path):
        (cid,) = m.groups()
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
    elif m := re.match(r"/@([^/]+)", u.path):
        (username,) = m.groups()
        feed_url = f"https://www.youtube.com/feeds/videos.xml?user={username}"
    else:
        return None
    try:
        with urlopen(feed_url, timeout=10) as resp:
            # print(f"{resp.status} {resp.reason} {feed_url}")
            if resp.status != 200:
                return None
            return _parse_channel_info(resp.read(), cid, username)
    except:
        return None


def _fetch_channel_info_fallback(url: str) -> Channel:
    from yt_dlp import YoutubeDL

    with YoutubeDL({"quiet": True, "logger": logging.getLogger()}) as ydl:
        info = ydl.extract_info(url, download=False, process=False)
        if not info or not isinstance(info, dict):
            raise Exception(f"Can't extract info by url: {url}")

        title = info.get("title", "Unknown")
        channel_id = info.get("channel_id")
        if not channel_id or len(channel_id) != 24:
            raise Exception(f"Invalid channel_id {channel_id!r}\ninfo: {info}")

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
