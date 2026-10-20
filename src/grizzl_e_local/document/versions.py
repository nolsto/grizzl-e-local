from __future__ import annotations

from typing import Annotated, ClassVar

from ..constants import Endpoint
from .base import BaseDocument
from .validation import ValidationError, PasswordLengthValidator


class CurrentRestraintValidator:
    fields = {"currentSet", "curDesign"}
    def __call__(self, doc: Version_01) -> None:
        if getattr(doc, "currentSet", 0) > getattr(doc, "curDesign", float('inf')):
            raise ValidationError(f"Device not designed to exceed {doc.curDesign} amps")


class HttpAuthValidator:
    fields = {"httpPassword", "httpUsername"}
    def __call__(self, doc: Version_01) -> None:
        if getattr(doc, "httpPassword", "") and not getattr(doc, "httpUsername", ""):
            raise ValidationError("httpUsername required when httpPassword is set")


class Version_01(BaseDocument):
    """Document for Firmware 01.XX"""

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
    pilot2: int
    pilot3: int
    state: int
    state2: int
    state3: int
    subState: int
    subState2: int
    subState3: int
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
    ground: int
    groundCtrl: int

    # --- Tariffs ---
    tarifAEnable: int
    tarifBEnable: int
    tarifAValue: int  # currency, smallest units (e.g. cents)
    tarifBValue: int  # currency, smallest units (e.g. cents)
    tarifAStart: int  # minutes from midnight
    tarifAStop: int   # minutes from midnight
    tarifBStart: int  # minutes from midnight
    tarifBStop: int   # minutes from midnight
    tarif: int        # currency, smallest units (e.g. cents)
    activeTarif: int

    # --- Timer ---
    timerType: int
    timeZone: int   # UTC offset in hours
    systemTime: int # epoch seconds
    timeMsg: int

    # --- Limits ---
    timeLimitS: int
    energyLimitS: int
    moneyLimitS: int
    evseEnabled: int
    suspendErrors: int
    suspendLimits: int
    oneCharge: int
    delayedLimit: int
    timeLimit: int  # seconds
    energyLimit: int
    moneyLimit: int  # currency, smallest units (e.g. cents)

    # --- Schedule 1 ---
    sh1Enabled: int
    sh1Start: int   # minutes from midnight
    sh1Stop: int    # minutes from midnight
    sh1CurrentEnable: int
    sh1CurrentValue: int
    sh1EnergyEnable: int
    sh1EnergyValue: int

    # --- Schedule 2 ---
    sh2Enabled: int
    sh2Start: int   # minutes from midnight
    sh2Stop: int    # minutes from midnight
    sh2CurrentEnable: int
    sh2CurrentValue: int
    sh2EnergyEnable: int
    sh2EnergyValue: int

    # --- Energy totals (read-only) ---
    totalEnergy: float
    totalEnergy2: float
    totalEnergy3: float
    sessionTime: int  # seconds
    sessionTime2: int  # seconds
    sessionTime3: int  # seconds
    sessionEnergy: float
    sessionEnergy2: float
    sessionEnergy3: float
    sessionMoney: float
    sessionMoney2: float
    sessionMoney3: float
    sessionStarted: int
    sessionStarted2: int
    sessionStarted3: int

    # --- Independent meters (read-only) ---
    IEM1: float
    IEM2: float
    IEM1_money: float
    IEM2_money: float

    # --- Measurements (read-only) ---
    curMeas1: int
    curMeas1C2: int
    curMeas1C3: int
    curMeas2: int
    curMeas3: int
    voltMeas1: int
    voltMeas2: int
    voltMeas3: int
    powerMeas: int
    powerMeas2: int
    powerMeas3: int
    temperature1: int   # degrees c
    temperature2: int   # degrees c
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
    scanComplete: int
    ocppconnected: int
    ocppEnabled: int
    ocppOfflineAva: int
    STA_IP_Addres: str  # device typo, preserved for compatibility
    RSSI: int
    logReady: int

    # --- Confirmation fields (write-only) ---
    ssidPasswordAPConf: str = ""
    httpPasswordConf: str = ""
    ssidPasswordConf: str = ""

    # --- Counter resets (write-only) ---
    rstEM1: None = None
    rstEM2: None = None

    # --- Other ---
    lang: int

    validators: ClassVar = [
        CurrentRestraintValidator(),
        PasswordLengthValidator("ssidPasswordAP"),
        PasswordLengthValidator("ssidPassword"),
        HttpAuthValidator(),
    ]

