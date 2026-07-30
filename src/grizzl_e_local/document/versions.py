from __future__ import annotations

from datetime import datetime, time, tzinfo
from decimal import Decimal
from typing import Annotated, ClassVar

from ..constants import Endpoint
from .base import BaseDocument
from .validation import ValidationError, PasswordLengthValidator


class CurrentRestraintValidator:
    fields = {"currentSet", "curDesign"}
    def __call__(self, doc: Document) -> None:
        if getattr(doc, "currentSet", 0) > getattr(doc, "curDesign", float('inf')):
            raise ValidationError(f"Device not designed to exceed {doc.curDesign} amps")


class HttpAuthValidator:
    fields = {"httpPassword", "httpUsername"}
    def __call__(self, doc: Document) -> None:
        if getattr(doc, "httpPassword", "") and not getattr(doc, "httpUsername", ""):
            raise ValidationError("httpUsername required when httpPassword is set")


class Version_01Document(BaseDocument):

    # --- Firmware (read-only) ---
    verFWMain: str
    verFWWifi: str
    serialNumCPU: str
    serialNum: str
    stationId: str
    fwCRC32: str
    verFWStatus: int

    # --- Status (read-only) ---
    pilot: int
    state: int
    subState: int
    currentSet: int
    curDesign: int
    minCurrent: int
    minVoltage: int
    gridRange: int
    typeEvse: int
    typeRelay: int
    aiModecurrent: int
    aiStatus: int

    # --- Adaptive (read-only) ---
    aiVoltage: int
    aiVoltageStart: int
    aiVoltageDrop: int
    aiPowerDrop: int
    aiMode: int = 0

    # --- Power/ground (read-only) ---
    SNflag: int
    ground: bool
    groundCtrl: int

    # --- Tariffs ---
    tarifAEnable: bool
    tarifBEnable: bool
    tarifAValue: Decimal
    tarifBValue: Decimal
    tarifAStart: time
    tarifAStop: time
    tarifBStart: time
    tarifBStop: time
    tarif: Decimal
    activeTarif: int

    # --- Timer ---
    timerType: int
    timeZone: tzinfo
    systemTime: datetime
    timeMsg: bool

    # --- Limits ---
    timeLimitS: bool
    energyLimitS: bool
    moneyLimitS: bool
    evseEnabled: bool
    suspendErrors: int
    suspendLimits: bool
    oneCharge: bool
    delayedLimit: int
    timeLimit: int
    energyLimit: int
    moneyLimit: int

    # --- Schedule 1 ---
    sh1Enabled: bool
    sh1Start: time
    sh1Stop: time
    sh1CurrentEnable: bool
    sh1CurrentValue: int
    sh1EnergyEnable: bool
    sh1EnergyValue: int

    # --- Schedule 2 ---
    sh2Enabled: bool
    sh2Start: time
    sh2Stop: time
    sh2CurrentEnable: bool
    sh2CurrentValue: int
    sh2EnergyEnable: bool
    sh2EnergyValue: int

    # --- Energy totals (read-only) ---
    totalEnergy: float
    sessionTime: int
    sessionEnergy: float
    sessionMoney: float
    sessionStarted: bool

    # --- Independent meters (read-only) ---
    IEM1: float
    IEM2: float
    IEM1_money: float
    IEM2_money: float

    # --- Measurements (read-only) ---
    curMeas1: int
    curMeas2: int
    curMeas3: int
    voltMeas1: int
    voltMeas2: int
    voltMeas3: int
    powerMeas: int
    temperature1: int
    temperature2: int
    leakValue: int
    leakValueH: int
    vBat: float
    adapter: int

    # --- Network (from /init, non-default endpoints) ---
    ssidNameAP: Annotated[str, Endpoint.CONFIG_AP]
    ssidPasswordAP: Annotated[str, Endpoint.CONFIG_AP]
    httpUsername: Annotated[str, Endpoint.CONFIG_HTTP]
    httpPassword: Annotated[str, Endpoint.CONFIG_HTTP]

    # --- Network (from /main) ---
    ssidName: str
    ssidPassword: str
    WifiMode: int
    ESP_MAC: str
    mac_bind: int
    STA_MAC: str
    scanComplete: bool
    ocppconnected: bool
    ocppEnabled: bool
    ocppOfflineAva: bool
    STA_IP_Addres: str  # device typo, preserved for compatibility
    RSSI: int
    logReady: bool

    # --- Confirmation fields (write-only) ---
    ssidPasswordAPConf: str = ""
    httpPasswordConf: str = ""
    ssidPasswordConf: str = ""

    # --- Other ---
    lang: int

    validators: ClassVar = [
        CurrentRestraintValidator(),
        PasswordLengthValidator("ssidPasswordAP"),
        PasswordLengthValidator("ssidPassword"),
        HttpAuthValidator(),
    ]


Document = Version_01Document  # type: ignore[assignment]
