from datetime import datetime, timedelta, timezone
from pytfeeder.models import Entry, Channel


sample_channel = Channel(channel_id="sample_channel_id1234567", title="Sample Channel")
sample_entries = [
    Entry(
        id=f"video_id_{i:02d}",
        title=f"Video #{i}",
        updated=datetime.now(timezone.utc) - timedelta(hours=25 * (3 - i)),
        channel_id="sample_channel_id1234567",
    )
    for i in range(3, 0, -1)
]

entry_fmt = """\t<entry>
\t\t<yt:videoId>{id}</yt:videoId>
\t\t<yt:channelId>{channel_id}</yt:channelId>
\t\t<title>{title}</title>
\t\t<updated>{updated}</updated>
\t</entry>"""

feed_fmt = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
\t<title>{channel_title}</title>
\t<link rel="alternate" href="https://www.youtube.com/channel/{channel_id}"/>
{entries}
</feed>"""

raw_feed = feed_fmt.format(
    channel_title=sample_channel.title,
    channel_id=sample_channel.channel_id,
    entries="".join(
        entry_fmt.format(
            id=e.id, title=e.title, updated=e.updated, channel_id=e.channel_id
        ).rstrip()
        for e in sample_entries
    ),
).strip()
