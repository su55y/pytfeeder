from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List


@dataclass
class Entry:
    id: str
    title: str
    updated: datetime = datetime.now(timezone.utc)
    channel_id: str = "Unknown"
    is_viewed: bool = False


@dataclass
class Channel:
    title: str = ""
    channel_id: str = ""
    entries: List[Entry] = field(default_factory=list)
    have_updates: bool = False
