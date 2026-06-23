"""Network configuration manager for AP, HTTP auth, and STA WiFi settings."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..managers import Manager

if TYPE_CHECKING:
    from ..client import Client

logger = logging.getLogger(__name__)


class NetworkManager(Manager):
    """Read and write network configuration (AP, HTTP auth, STA WiFi)."""

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    async def get_config(self) -> dict[str, Any]:
        """Return a dict of all network-related fields from the current document."""
        doc = await self._client.get_document()
        return {
            "ssidNameAP": doc.ssidNameAP,
            "ssidPasswordAP": doc.ssidPasswordAP,
            "ssidName": doc.ssidName,
            "ssidPassword": doc.ssidPassword,
            "httpUsername": doc.httpUsername,
            "httpPassword": doc.httpPassword,
            "WifiMode": doc.WifiMode,
            "ESP_MAC": doc.ESP_MAC,
            "mac_bind": doc.mac_bind,
            "STA_MAC": doc.STA_MAC,
        }

    # ------------------------------------------------------------------
    # AP WiFi config (/configAP)
    # ------------------------------------------------------------------

    async def set_ap(
        self,
        ssid_name_ap: str,
        ssid_password_ap: str,
        ssid_password_ap_conf: str | None = None,
    ) -> None:
        """Write AP WiFi settings.

        The device requires ``ssidPasswordAPConf`` to match
        ``ssidPasswordAP``.  Pass it explicitly or it defaults to the
        password value.
        """
        conf = ssid_password_ap_conf or ssid_password_ap
        await self.set(
            ssidNameAP=ssid_name_ap,
            ssidPasswordAP=ssid_password_ap,
            ssidPasswordAPConf=conf,
        )

    # ------------------------------------------------------------------
    # HTTP auth config (/configHttp)
    # ------------------------------------------------------------------

    async def set_http(
        self,
        http_username: str,
        http_password: str,
        http_password_conf: str | None = None,
    ) -> None:
        """Write HTTP login/password settings.

        Triggers a device reboot and session invalidation, just like
        setting ``httpUsername`` or ``httpPassword`` individually.
        """
        conf = http_password_conf or http_password
        await self.set(
            httpUsername=http_username,
            httpPassword=http_password,
            httpPasswordConf=conf,
        )

    # ------------------------------------------------------------------
    # STA WiFi config (/config)
    # ------------------------------------------------------------------

    async def set_sta(
        self,
        ssid_name: str,
        ssid_password: str,
        ssid_password_conf: str | None = None,
        wifi_mode: int | None = None,
        mac_bind: int | None = None,
        sta_mac: str | None = None,
    ) -> None:
        """Write STA (router) WiFi settings.

        All fields are optional except ``ssid_name`` and
        ``ssid_password``.  Only the fields you pass will be written.
        """
        conf = ssid_password_conf or ssid_password
        data: dict[str, Any] = {
            "ssidName": ssid_name,
            "ssidPassword": ssid_password,
            "ssidPasswordConf": conf,
        }
        if wifi_mode is not None:
            data["WifiMode"] = wifi_mode
        if mac_bind is not None:
            data["mac_bind"] = mac_bind
        if sta_mac is not None:
            data["STA_MAC"] = sta_mac
        await self.set(**data)
