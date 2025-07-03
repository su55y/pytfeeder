from pytfeeder.models import Channel

raw_channels_yaml_mock = """
- {channel_id: abcdefghijklmnopqrstuvw0, title: Channel 1}
- {channel_id: abcdefghijklmnopqrstuvw1, hidden: true, tags: [foo, bar], title: Channel 2}
""".lstrip()

channels_mock = [
    Channel(channel_id="abcdefghijklmnopqrstuvw0", title="Channel 1"),
    Channel(
        channel_id="abcdefghijklmnopqrstuvw1",
        hidden=True,
        tags=["foo", "bar"],
        title="Channel 2",
    ),
]
