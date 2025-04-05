from dataclasses import dataclass, field
import datetime as dt
from typing import List, Dict


@dataclass
class Entry:
    id: str
    title: str
    channel_id: str
    published: dt.datetime = dt.datetime.now(dt.timezone.utc)
    is_viewed: bool = False

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


@dataclass
class Channel:
    title: str = ""
    channel_id: str = ""
    entries: List[Entry] = field(default_factory=list)
    have_updates: bool = False

    def __post_init__(self) -> None:
        if self.title == "":
            raise InvalidChannelError(f"Invalid title {self.title!r}")
        if len(self.channel_id) != 24 and self.channel_id != "feed":
            raise InvalidChannelError(
                f"Invalid channel_id {len(self.channel_id) = } ({self.channel_id!r}), should be 24)"
            )

    def dump(self) -> Dict:
        return {"title": self.title, "channel_id": self.channel_id}
