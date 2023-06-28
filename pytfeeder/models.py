from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List


@dataclass
class Entry:
    id: str
    title: str
    updated: str = str(datetime.now(timezone.utc))
    is_viewed: bool = False


@dataclass
class Channel:
    title: str = ""
    channel_id: str = ""
    entries: List[Entry] = field(default_factory=list)
