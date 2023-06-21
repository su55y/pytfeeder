from pytfeeder.models import Entry, Channel

entry_fmt = """
\t<entry>
\t\t<yt:videoId>{id}</yt:videoId>
\t\t<title>{title}</title>
\t\t<updated>{updated}</updated>
\t</entry>
"""
feed_fmt = """
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
\t<title>{channel_title}</title>
\t<link rel="alternate" href="https://www.youtube.com/channel/{channel_id}"/>
{entries}
</feed>
"""


sample_channel = Channel(channel_id="sample_channel_id1234567", title="Sample Channel")
sample_entries = [
    Entry(
        id=f"video_id_{n:02d}",
        title=f"Video #{n}",
        updated=f"2023-01-{n:02d}T00:00:00+00:00",
    )
    for n in range(3, 0, -1)
]
raw_feed = feed_fmt.format(
    channel_title=sample_channel.title,
    channel_id=sample_channel.channel_id,
    entries="".join(
        entry_fmt.format(id=e.id, title=e.title, updated=e.updated).rstrip()
        for e in sample_entries
    ),
).strip()
