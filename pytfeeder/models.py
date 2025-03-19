from dataclasses import dataclass, field
import datetime as dt
from typing import List, Dict


@dataclass
class Entry:
    id: str
    title: str
    published: dt.datetime = dt.datetime.now(dt.timezone.utc)
    channel_id: str = "Unknown"
    is_viewed: bool = False

    def __eq__(self, obj: "Entry") -> bool:
        return (
            obj.id == self.id
            and obj.title == self.title
            and obj.channel_id == self.channel_id
        )


@dataclass
class Channel:
    title: str = ""
    channel_id: str = ""
    entries: List[Entry] = field(default_factory=list)
    have_updates: bool = False

    def dump(self) -> Dict:
        return {"title": self.title, "channel_id": self.channel_id}
