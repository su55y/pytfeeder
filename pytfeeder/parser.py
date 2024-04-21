import datetime as dt
import logging
import re
from typing import List, Optional
import xml.etree.ElementTree as ET

from .models import Entry


class YTFeedParser:
    def __init__(self, raw) -> None:
        self.__schema = "{http://www.w3.org/2005/Atom}%s"
        self.__namespace = {"yt": "http://www.youtube.com/xml/schemas/2015"}
        self.__tree = ET.fromstring(raw)

        self.__entries: List[Entry] = []
        self.log = logging.getLogger()
        self.rx_id = re.compile(r"^[A-Za-z0-9\-_]{11}$")
        self.rx_channel_id = re.compile(r"^[A-Za-z0-9\-_]{24}$")
        self.rx_updated = re.compile(
            r"^\d{4}-\d{2}-\d{2}[T\s]\d{2}\:\d{2}\:\d{2}\+\d{2}\:\d{2}$"
        )
        self.default_updated = dt.datetime.now(dt.timezone.utc)

        self._read_entries()

    @property
    def entries(self) -> List[Entry]:
        return self.__entries

    def _read_entries(self):
        for entry in self.__tree.findall(self.__schema % "entry"):
            id = self._read_yt_tag("yt:videoId", entry)
            if id is None or not self.rx_id.match(id):
                self.log.error(f"invalid id {id!r} in entry: {entry!r}")
                continue
            channel_id = self._read_yt_tag("yt:channelId", entry)
            if channel_id is None or not self.rx_channel_id.match(channel_id):
                self.log.error(f"invalid channel_id {channel_id!r} in entry: {entry!r}")
                continue
            title = self._read_tag(self.__schema % "title", entry) or "-"
            updated = self._read_tag(self.__schema % "updated", entry)
            if updated is not None and self.rx_updated.match(updated):
                updated = dt.datetime.fromisoformat(updated)
            else:
                updated = self.default_updated
            self.__entries.append(
                Entry(id=id, title=title, updated=updated, channel_id=channel_id)
            )

    def _read_tag(self, name: str, el: Optional[ET.Element] = None) -> Optional[str]:
        tag = self.__tree.find(name) if not el else el.find(name)
        if tag is not None:
            return tag.text
        self.log.error(f"can't read {name} tag")

    def _read_yt_tag(self, name: str, el: Optional[ET.Element] = None) -> Optional[str]:
        tag = (
            self.__tree.find(name, self.__namespace)
            if not el
            else el.find(name, self.__namespace)
        )
        if tag is not None:
            return tag.text
        self.log.error(f"can't read {name} tag")
