import datetime as dt
import logging
import re
from xml.etree.ElementTree import XML

from .models import Entry

rx_id = re.compile(r"^[A-Za-z0-9\-_]{11}$")
rx_channel_id = re.compile(r"^[A-Za-z0-9\-_]{24}$")
rx_datetime = re.compile(r"^\d{4}-\d{2}-\d{2}[T\s]\d{2}\:\d{2}\:\d{2}\+\d{2}\:\d{2}$")

SCHEMA = "{http://www.w3.org/2005/Atom}%s"
NAMESPACE = {"yt": "http://www.youtube.com/xml/schemas/2015"}


class YTFeedParser:
    def __init__(
        self,
        raw: str,
        *,
        skip_shorts: bool = False,
        log: logging.Logger | None = None,
    ) -> None:
        self.log = log or logging.getLogger()
        self.default_published = dt.datetime.now(dt.timezone.utc)
        self.skip_shorts = skip_shorts
        self.__tree = XML(text=raw)
        self.__entries: list[Entry] = list()

        self.__parse_entries()

    @property
    def entries(self) -> list[Entry]:
        return self.__entries

    def __parse_entries(self):
        for entry in self.__tree.findall(SCHEMA % "entry"):
            link = entry.find(SCHEMA % "link")
            if link is not None and link.attrib.get("rel") == "alternate":
                is_shorts = link.attrib.get("href", "").find("/shorts/") != -1
                if self.skip_shorts and is_shorts:
                    continue
            id_ = entry.findtext("yt:videoId", namespaces=NAMESPACE)
            if id_ is None or not rx_id.match(id_):
                self.log.error(f"invalid id {id_!r} in entry: {entry!r}")
                continue

            channel_id = entry.findtext("yt:channelId", namespaces=NAMESPACE)
            if channel_id is None or not rx_channel_id.match(channel_id):
                self.log.error(f"invalid channel_id {channel_id!r} in entry: {entry!r}")
                continue

            title = entry.findtext(SCHEMA % "title", default="Unknown")

            published = entry.findtext(SCHEMA % "published")
            if published and rx_datetime.match(published):
                published = dt.datetime.fromisoformat(published)
            else:
                published = self.default_published

            self.__entries.append(
                Entry(
                    id=id_,
                    title=title,
                    published=published,
                    channel_id=channel_id,
                )
            )
