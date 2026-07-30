"""Endpoint paths and other shared constants."""

from enum import Enum

class Endpoint(Enum):
    GET = "/main"
    SET = "/pageEvent"
    INIT = "/init"
    CONFIG_AP = "/configAP"
    CONFIG_HTTP = "/configHttp"
    CONFIG = "/config"
