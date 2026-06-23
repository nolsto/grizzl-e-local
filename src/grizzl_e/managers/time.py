from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

from ..managers import Manager

if TYPE_CHECKING:
    from ..client import Client


class TimeManager(Manager):
    """Manages device timezone and system time as timezone-aware datetimes."""

    async def get_time(self) -> datetime:
        """Read the device's current time as a timezone-aware datetime."""
        doc = await self._client.get_document()

        offset_hours = doc.timeZone
        tz = timezone(timedelta(hours=offset_hours))
        return datetime.fromtimestamp(doc.systemTime, tz=tz)

    async def set_time(self, dt: datetime) -> None:
        """Set the device's timezone and system time from a timezone-aware datetime."""
        if dt.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")

        offset = dt.utcoffset()
        if offset is None:
            raise ValueError("datetime must have a valid UTC offset")

        offset_hours = int(offset.total_seconds() // 3600)
        unix_ts = int(dt.timestamp())

        await self.set(
            timeZone=offset_hours,
            systemTime=unix_ts,
        )
