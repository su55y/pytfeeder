from pytfeeder.models import Channel

raw_channels_yaml_mock = """
- {channel_id: abcdefghijklmnopqrstuvw0, title: Channel 1}
- {channel_id: abcdefghijklmnopqrstuvw1, title: Channel 2}
""".lstrip()

channels_mock = [
    Channel(channel_id="abcdefghijklmnopqrstuvw0", title="Channel 1"),
    Channel(channel_id="abcdefghijklmnopqrstuvw1", title="Channel 2"),
]
