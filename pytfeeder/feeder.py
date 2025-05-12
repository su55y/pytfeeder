from functools import lru_cache, cached_property
import logging
import time

import asyncio
from aiohttp import ClientSession

from .config import Config
from .models import Channel, Entry
from .parser import YTFeedParser
from .storage import Storage

YT_FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id=%s"


class Feeder:
    def __init__(
        self,
        config: Config,
        storage: Storage,
        log: logging.Logger | None = None,
    ) -> None:
        self.stor = storage
        self.config = config
        self.log = log or logging.getLogger()
        self.__channels_map = {c.channel_id: c for c in self.config.channels}

    @cached_property
    def channels(self) -> list[Channel]:
        self.refresh_channels()
        return self.config.channels

    def refresh_channels(self) -> None:
        stats = self.stor.select_channels_stats()
        for c in self.config.channels:
            stat = stats.get(c.channel_id)
            if stat is None:
                self.log.warning(f"No stats for {c!r} in db")
                continue
            count, unwatched = stat
            c.entries_count = count
            c.have_updates = bool(unwatched)
            c.unwatched_count = unwatched

    @lru_cache
    def channel(self, channel_id: str) -> Channel | None:
        return self.__channels_map.get(channel_id)

    @lru_cache
    def channel_title(self, channel_id: str) -> str:
        return c.title if (c := self.channel(channel_id)) else "Unknown"

    def channel_feed(
        self,
        channel_id: str,
        limit: int | None = None,
        unwatched_first: bool | None = None,
    ) -> list[Entry]:
        return self.stor.select_entries(
            channel_id=channel_id,
            limit=limit,
            unwatched_first=unwatched_first,
        )

    def feed(
        self,
        limit: int | None = None,
        unwatched_first: bool | None = None,
        include_unknown: bool = False,
    ) -> list[Entry]:
        return self.stor.select_entries(
            limit=limit,
            unwatched_first=unwatched_first,
            in_channels=None if include_unknown else self.config.channels,
        )

    def mark_as_watched(
        self,
        id: str | None = None,
        channel_id: str | None = None,
        unwatched: bool = False,
    ) -> None:
        if id:
            self.stor.mark_entry_as_watched(id, unwatched)
        elif channel_id:
            self.stor.mark_channel_entries_as_watched(channel_id, unwatched)
        else:
            self.stor.mark_all_entries_as_watched(unwatched)

    def mark_entry_as_deleted(self, id: str) -> bool:
        try:
            return self.stor.mark_entry_as_deleted(id)
        except Exception as e:
            self.log.error(f"Can't mark entry as deleted: {e!r}")
            return False

    def total_entries_count(self) -> int:
        return self.stor.select_entries_count()

    def deleted_count(self) -> int:
        return self.stor.select_entries_count(is_deleted=True)

    def unwatched_count(self, channel_id: str | None = None) -> int:
        return self.stor.select_entries_count(
            channel_id=channel_id,
            is_watched=False,
            is_deleted=False,
        )

    def clean_cache(self) -> int:
        count = self.stor.delete_old_entries()
        self.stor.execute_vacuum()
        return count

    async def sync_entries(self) -> tuple[int, Exception | None]:
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
    ) -> tuple[int, Exception | None]:
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
        parser = YTFeedParser(raw_feed, log=self.log)
        if not len(parser.entries):
            self.log.error(f"can't parse feed for {channel_id}\n{raw_feed[:80] = !r}")
            return 0
        return self.stor.add_entries(parser.entries)

    async def _fetch_feed(self, session: ClientSession, channel_id: str) -> str:
        url = YT_FEED_URL % channel_id
        async with session.get(url) as resp:
            self.log.debug(f"{resp.status} {resp.reason} {resp.url}")
            if resp.status == 200:
                return await resp.text()
            raise Exception(f"{resp.status} {resp.reason} {resp.url}")

    def update_lock_file(self) -> None:
        try:
            self.config.lock_file.write_text(time.strftime("%s"))
        except Exception as e:
            self.log.error(repr(e))
