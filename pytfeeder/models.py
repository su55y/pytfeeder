from dataclasses import dataclass, field
from typing import List


@dataclass
class Entry:
    id: str
    title: str
    updated: str
    is_viewed: bool = False

@dataclass
class Channel:
    title: str = ""
    channel_id: str = ""
    entries: List[Entry] = field(default_factory=list)
