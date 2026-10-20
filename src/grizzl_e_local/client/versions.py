from __future__ import annotations

from ..document.versions import Version_01 as Document
from ..device.state import Version_01 as DeviceState
from ..device.versions import Version_01 as Device
from .base import BaseClient


class Version_01(BaseClient[Document, Device]):
    """Client for Firmware 01.XX"""

    document_class = Document
    device_class = Device

    @property
    def device(self) -> DeviceState:
        return super().device
