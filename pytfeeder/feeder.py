from functools import lru_cache, cached_property
import logging
from typing import List, Optional

import asyncio
from aiohttp import ClientSession

from .config import Config
from .consts import YT_FEED_URL
from .models import Channel, Entry
from .parser import YTFeedParser
from .storage import Storage


class Feeder:
    def __init__(self, config: Config, storage: Storage) -> None:
        self.stor = storage
        self.config = config
        self.log = logging.getLogger()
        self.__channels_map = {c.channel_id: c for c in self.config.channels}

    @cached_property
    def channels(self) -> List[Channel]:
        for i in range(len(self.config.channels)):
            self.config.channels[i].have_updates = bool(
                self.stor.select_unviewed(self.config.channels[i].channel_id)
            )
        return self.config.channels

    def update_channels(self) -> List[Channel]:
        for i in range(len(self.config.channels)):
            self.config.channels[i].have_updates = bool(
                self.stor.select_unviewed(self.config.channels[i].channel_id)
            )
        return self.config.channels

    @lru_cache
    def channel(self, channel_id: str) -> Optional[Channel]:
        return self.__channels_map.get(channel_id)

    @lru_cache
    def channel_title(self, channel_id: str) -> str:
        return c.title if (c := self.channel(channel_id)) else "Unknown"

    def channel_feed(self, channel_id: str, limit: Optional[int] = None) -> List[Entry]:
        return self.stor.select_entries(
            channel_id=channel_id,
            limit=limit or self.config.channel_feed_limit,
            unviewed_first=self.config.unviewed_first,
        )

    def feed(self, limit: Optional[int] = None) -> List[Entry]:
        return self.stor.select_entries(
            limit=limit or self.config.feed_limit,
            unviewed_first=self.config.unviewed_first,
        )

    def mark_as_viewed(
        self,
        id: Optional[str] = None,
        channel_id: Optional[str] = None,
        unviewed: bool = False,
    ) -> None:
        if id:
            self.stor.mark_entry_as_viewed(id, unviewed)
        elif channel_id:
            self.stor.mark_channel_entries_as_viewed(channel_id, unviewed)
        else:
            self.stor.mark_all_entries_as_viewed(unviewed)

    def unviewed_count(self, channel_id: Optional[str] = None) -> int:
        return self.stor.select_unviewed(channel_id)

    def clean_cache(self, force=False) -> None:
        self.stor.delete_all_entries(force)
        self.stor.delete_inactive_channels(
            ", ".join(f"{c.channel_id!r}" for c in self.config.channels)
        )

    async def sync_entries(self) -> None:
        async with ClientSession() as session:
            await asyncio.gather(
                *[
                    asyncio.create_task(self._fetch_and_sync_entries(session, channel))
                    for channel in self.config.channels
                ]
            )

    async def _fetch_and_sync_entries(
        self, session: ClientSession, channel: Channel
    ) -> None:
        raw_feed = await self._fetch_feed(session, channel.channel_id)
        if not raw_feed:
            self.log.error("can't fetch feed for '%s'" % channel.title)
            return
        try:
            parser = YTFeedParser(raw_feed)
        except:
            self.log.error("can't parse feed for '%s'" % channel.title)
        else:
            if count := self.stor.add_entries(parser.entries):
                self.log.info("%d new entries for '%s'" % (count, channel.title))

    async def _fetch_feed(
        self, session: ClientSession, channel_id: str
    ) -> Optional[str]:
        url = YT_FEED_URL % channel_id
        async with session.get(url) as resp:
            self.log.debug(f"{resp.status} {resp.reason} {resp.url}")
            if resp.status == 200:
                return await resp.text()
