import subprocess as sp

from .models import Channel, Entry


def fetch_channel_info(url: str) -> Channel:
    from yt_dlp import YoutubeDL

    with YoutubeDL({"quiet": True}) as ydl:
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


def download_video(entry: Entry, output: str, send_notification=True) -> None:
    p = sp.check_output(
        [
            "tsp",
            "yt-dlp",
            f"https://youtu.be/{entry.id}",
            "-o",
            output,
        ],
        shell=False,
    )

    if send_notification:
        _ = notify(f"⬇️Start downloading {entry.title!r}...")

    _ = sp.run(
        [
            "tsp",
            "-D",
            p.decode(),
            "notify-send",
            "-i",
            "youtube",
            "-a",
            "pytfeeder",
            f"✅Download done: {entry.title}",
        ],
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL,
    )


def play_video(entry: Entry) -> None:
    notify(f"{entry.title} playing...")
    sp.Popen(
        [
            "setsid",
            "-f",
            "mpv",
            "https://youtu.be/%s" % entry.id,
            "--ytdl-raw-options=retries=infinite",
        ],
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL,
    )


def notify(msg: str) -> bool:
    if not msg:
        return True
    cmd = ["notify-send", "-i", "youtube", "-a", "pytfeeder", msg]
    p = sp.run(cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    if p.returncode != 0:
        return False
    return True


def download_all(entries: list[Entry], output: str) -> None:
    _ = notify(f"⬇️Start downloading {len(entries)} entries...")
    for e in entries:
        download_video(e, output, send_notification=False)
