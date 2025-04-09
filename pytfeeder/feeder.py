from functools import lru_cache, cached_property
import logging
import time
from typing import List, Optional, Tuple

import asyncio
from aiohttp import ClientSession

from .config import Config
from .models import Channel, Entry
from .parser import YTFeedParser
from .storage import Storage

YT_FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id=%s"


class Feeder:
    def __init__(self, config: Config, storage: Storage) -> None:
        self.stor = storage
        self.config = config
        self.log = logging.getLogger()
        self.__channels_map = {c.channel_id: c for c in self.config.channels}

    @cached_property
    def channels(self) -> List[Channel]:
        self.refresh_channels()
        return self.config.channels

    def refresh_channels(self) -> None:
        for i in range(len(self.config.channels)):
            self.config.channels[i].have_updates = bool(
                self.stor.select_unwatched(self.config.channels[i].channel_id)
            )

    @lru_cache
    def channel(self, channel_id: str) -> Optional[Channel]:
        return self.__channels_map.get(channel_id)

    @lru_cache
    def channel_title(self, channel_id: str) -> str:
        return c.title if (c := self.channel(channel_id)) else "Unknown"

    def channel_feed(
        self,
        channel_id: str,
        limit: Optional[int] = None,
        unwatched_first: Optional[bool] = None,
    ) -> List[Entry]:
        return self.stor.select_entries(
            channel_id=channel_id,
            limit=limit,
            unwatched_first=unwatched_first,
        )

    def feed(
        self,
        limit: Optional[int] = None,
        unwatched_first: Optional[bool] = None,
    ) -> List[Entry]:
        return self.stor.select_entries(
            limit=limit,
            unwatched_first=unwatched_first,
        )

    def mark_as_watched(
        self,
        id: Optional[str] = None,
        channel_id: Optional[str] = None,
        unwatched: bool = False,
    ) -> None:
        if id:
            self.stor.mark_entry_as_watched(id, unwatched)
        elif channel_id:
            self.stor.mark_channel_entries_as_watched(channel_id, unwatched)
        else:
            self.stor.mark_all_entries_as_watched(unwatched)

    def unwatched_count(self, channel_id: Optional[str] = None) -> int:
        if channel_id == "feed":
            return self.stor.select_unwatched()
        return self.stor.select_unwatched(channel_id)

    def clean_cache(self, force=False) -> None:
        self.stor.delete_all_entries(force)
        self.stor.delete_inactive_channels(
            ", ".join(f"{c.channel_id!r}" for c in self.config.channels)
        )

    async def sync_entries(self) -> Tuple[int, Optional[Exception]]:
        try:
            r = await self._sync_entries()
        except Exception as e:
            return 0, e
        else:
            return r, None
        finally:
            self.update_lock_file()

    async def _sync_entries(self) -> int:
        async with ClientSession() as s:
            tasks = [
                asyncio.create_task(self._sync_channel(s, c))
                for c in self.config.channels
            ]
            results = await asyncio.gather(*tasks)
            sum_of_new = 0
            for new, err in results:
                if err is not None:
                    raise err
                sum_of_new += new
            return sum_of_new

    async def _sync_channel(
        self, session: ClientSession, channel: Channel
    ) -> Tuple[int, Optional[Exception]]:
        try:
            self.log.debug(f"trying to sync {channel.title!r} ({channel.channel_id!r})")
            count = await self._fetch_and_sync_entries(session, channel.channel_id)
        except Exception as e:
            self.log.error(f"cannot sync channel ({channel.channel_id}): {e}")
            return 0, e
        else:
            if count > 0:
                self.log.info(
                    "%d new entries for %r (%r)"
                    % (count, channel.title, channel.channel_id)
                )
            return count, None

    async def _fetch_and_sync_entries(
        self, session: ClientSession, channel_id: str
    ) -> int:
        raw_feed = await self._fetch_feed(session, channel_id)
        if not raw_feed:
            self.log.error("can't fetch feed for '%s'" % channel_id)
            return 0
        parser = YTFeedParser(raw_feed, log=self.log)
        if not len(parser.entries):
            self.log.error(f"can't parse feed for {channel_id}\n{raw_feed[:80] = !r}")
            return 0
        return self.stor.add_entries(parser.entries)

    async def _fetch_feed(
        self, session: ClientSession, channel_id: str
    ) -> Optional[str]:
        url = YT_FEED_URL % channel_id
        async with session.get(url) as resp:
            self.log.debug(f"{resp.status} {resp.reason} {resp.url}")
            if resp.status == 200:
                return await resp.text()

    def update_lock_file(self) -> None:
        try:
            self.config.lock_file.write_text(time.strftime("%s"))
        except Exception as e:
            self.log.error(repr(e))
