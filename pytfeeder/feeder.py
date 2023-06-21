from functools import cached_property
import logging
from typing import List, Optional

import asyncio
from aiohttp import ClientSession

from .config import Config
from .models import Channel, Entry
from .parser import YTFeedParser
from .storage import Storage


class Feeder:
    def __init__(self, config: Config, storage: Storage) -> None:
        self.stor = storage
        self.config = config
        self.log = logging.getLogger()

    @cached_property
    def channels(self) -> List[Channel]:
        self.sync_channels()
        return self.config.channels

    def channel_feed(self, channel_id: str, limit: Optional[int] = None) -> List[Entry]:
        return self.stor.select_entries(
            channel_id=channel_id,
            limit=limit or self.config.channel_feed_limit,
        )

    def common_feed(self, limit: Optional[int] = None) -> List[Entry]:
        return self.stor.select_entries(limit=limit or self.config.common_feed_limit)

    def sync_channels(self) -> None:
        if new_channels_count := self.stor.add_channels(self.config.channels):
            self.log.info("%d new channels added" % new_channels_count)
        active_channels_ids = [(c.channel_id,) for c in self.config.channels]
        active_count = self.stor.update_active_channels(active_channels_ids)
        if active_count != len(self.config.channels):
            self.log.warning(
                "mismatch storage with config active channels: %d != %d"
                % (active_count, len(active_channels_ids)),
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
            if count := self.stor.add_entries(parser.entries, channel.channel_id):
                self.log.info("%d new entries for '%s'" % (count, channel.title))

    async def _fetch_feed(
        self, session: ClientSession, channel_id: str
    ) -> Optional[str]:
        url = "https://www.youtube.com/feeds/videos.xml?channel_id=%s" % channel_id
        async with session.get(url) as resp:
            self.log.debug(f"{resp.status} {resp.reason} {resp.url}")
            if resp.status == 200:
                return await resp.text()
