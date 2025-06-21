from dataclasses import dataclass, field
import datetime as dt
from typing import Any

import yaml


@dataclass
class Entry:
    id: str
    title: str
    channel_id: str
    published: dt.datetime = dt.datetime.now(dt.timezone.utc)
    is_viewed: bool = False
    is_deleted: bool = False

    def __eq__(self, obj: object) -> bool:
        if not isinstance(obj, Entry):
            return False
        return (
            obj.id == self.id
            and obj.title == self.title
            and obj.channel_id == self.channel_id
        )


class InvalidChannelError(ValueError):
    pass


class ChannelDumper(yaml.SafeDumper):
    pass


@dataclass
class Channel:
    title: str = ""
    channel_id: str = ""
    entries: list[Entry] = field(default_factory=list)
    entries_count: int = 0
    have_updates: bool = False
    hidden: bool = False
    tags: list[str] = field(default_factory=list)
    unwatched_count: int = 0

    def __post_init__(self) -> None:
        if self.title == "":
            raise InvalidChannelError(f"Invalid title {self.title!r}")
        if len(self.channel_id) != 24 and self.channel_id not in ["feed", "tag"]:
            raise InvalidChannelError(
                f"Invalid channel_id {len(self.channel_id) = } ({self.channel_id!r}), should be 24)"
            )

    @staticmethod
    def to_yaml(dumper: ChannelDumper, c: "Channel") -> yaml.MappingNode:
        d: dict[str, Any] = {"channel_id": c.channel_id, "title": c.title}
        if c.hidden == True:
            d["hidden"] = c.hidden
        return dumper.represent_mapping("tag:yaml.org,2002:map", d, flow_style=True)


@dataclass
class Tag:
    title: str = field(hash=True)
    channels: list[Channel] = field(default_factory=list)
    entries_count: int = 0
    have_updates: bool = False
    unwatched_count: int = 0
