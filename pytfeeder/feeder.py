import datetime as dt
from functools import lru_cache, cached_property
import logging
import time

import asyncio
from aiohttp import ClientSession

from .config import Config
from .models import Channel, Entry, Tag
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
        self.__channels_map = {c.channel_id: c for c in self.config.all_channels}

    @cached_property
    def channels(self) -> list[Channel]:
        self.refresh_channels_stats()
        return self.config.channels

    def refresh_channels_stats(self) -> None:
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

    def _reset_channels(self) -> None:
        try:
            del self.channels
        except AttributeError:
            pass
        except Exception:
            raise

    def channels_aplhabetic_sort(self) -> None:
        self._reset_channels()
        self.config.channels.sort(key=lambda c_: c_.title.lower())

    def channels_unwatched_first_sort(self) -> None:
        self._reset_channels()
        self.refresh_channels_stats()
        self.config.channels.sort(key=lambda c: not c.have_updates)

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

    @cached_property
    def tags_map(self) -> dict[str, Tag]:
        d: dict[str, Tag] = {}
        for c in self.channels:
            for t in c.tags:
                if t not in d:
                    d[t] = Tag(title=t)
                d[t].channels.append(c)
                d[t].entries_count += c.entries_count
                d[t].unwatched_count += c.unwatched_count
                d[t].have_updates |= c.have_updates
        return d

    @property
    def last_update(self) -> dt.datetime | None:
        if not self.config.lock_file.exists():
            self.log.warning(f"lock_file not found at {self.config.lock_file}")
            return None
        try:
            return dt.datetime.fromtimestamp(float(self.config.lock_file.read_text()))
        except Exception as e:
            self.log.error(f"Can't read timestamp from lock_file: {e!r}")
            return None

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
        return self.stor.mark_entry_as_deleted(id)

    def mark_channel_as_deleted(self, channel_id: str) -> int:
        return self.stor.mark_channel_entries_as_deleted(channel_id)

    def total_entries_count(self, exclude_hidden: bool = False) -> int:
        return self.stor.select_entries_count(
            is_deleted=False,
            in_channels=self.config.channels if exclude_hidden else None,
        )

    def deleted_count(self) -> int:
        return self.stor.select_entries_count(is_deleted=True)

    def unwatched_count(self, channel_id: str | None = None) -> int:
        return self.stor.select_entries_count(
            channel_id=channel_id,
            is_watched=False,
            is_deleted=False,
            in_channels=None if channel_id else self.config.channels,
        )

    def restore_channel(self, c: Channel) -> int:
        return self.stor.restore_channel(c)

    def channels_with_deleted(self) -> list[Channel]:
        channels = []
        for c_id, count in self.stor.select_channels_with_deleted():
            c = self.__channels_map.get(c_id)
            if c is None or c.hidden:
                continue
            channels.append(
                Channel(
                    title=f"{c.title} ({count} deleted)",
                    channel_id=c.channel_id,
                    entries_count=c.entries_count,
                )
            )
        return channels

    def clean_cache(self) -> int:
        count = self.stor.delete_old_entries()
        self.stor.execute_vacuum()
        return count

    def delete_inactive(self) -> int:
        count = self.stor.delete_inactive_channels(self.config.all_channels)
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
                for c in self.config.all_channels
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
        parser = YTFeedParser(
            raw_feed, skip_shorts=self.config.skip_shorts, log=self.log
        )
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
