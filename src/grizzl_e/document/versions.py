from typing import TYPE_CHECKING, Annotated, ClassVar, Self

from pydantic import Field

from ..constants import CONFIG_AP_PATH, CONFIG_HTTP_PATH, CONFIG_PATH
from .base import BaseDocument
from .fields import BoolInt, FrozenBoolInt, Currency, DateTime, Time, TimeZone
from .validation import ValidationError, PasswordLengthValidator

if TYPE_CHECKING:
    from .validation import Validator


class CurrentRestraintValidator:
    fields: set[str] = {"currentSet", "curDesign"}

    def __call__(self, doc: 'Version_01') -> None:
        if doc.currentSet > doc.curDesign:
            raise ValidationError(
                f"Device is not designed to exceed {doc.curDesign} amps",
            )


class HttpAuthValidator:
    fields: set[str] = {"httpPassword", "httpUsername"}

    def __call__(self, doc: 'Version_01') -> None:
        if doc.httpPassword and not doc.httpUsername:
            raise ValidationError("httpUsername is required when httpPassword is set")


class Version_01(BaseDocument):
    "Base document for Firmware 01.XX"

    # --- Firmware (read-only) ---
    verFWMain: str = Field(frozen=True)
    verFWWifi: str = Field(frozen=True)
    serialNumCPU: str = Field(frozen=True)
    serialNum: str = Field(frozen=True)
    fwCRC32: str = Field(frozen=True)
    verFWStatus: int = Field(frozen=True)

    # --- Status (read-only) ---
    pilot: int = Field(frozen=True)
    state: int = Field(frozen=True)
    subState: int = Field(frozen=True)
    currentSet: int
    curDesign: int = Field(frozen=True)
    minCurrent: int = Field(frozen=True)
    minVoltage: int
    gridRange: int = Field(frozen=True)
    typeEvse: int = Field(frozen=True)
    typeRelay: int = Field(frozen=True)
    aiModecurrent: int = Field(frozen=True)
    aiStatus: int = Field(frozen=True)

    # --- Adaptive (read-only) ---
    aiVoltage: int = Field(frozen=True)
    aiVoltageStart: int = Field(frozen=True)
    aiVoltageDrop: int = Field(frozen=True)
    aiPowerDrop: int = Field(frozen=True)
    aiMode: int = 0  # not in main.json but used by device

    # --- Power/ground (read-only) ---
    SNflag: int = Field(frozen=True)
    ground: FrozenBoolInt
    groundCtrl: int = Field(frozen=True)

    # --- Tariffs ---
    tarif: Currency
    activeTarif: int
    tarifAEnable: BoolInt
    tarifBEnable: BoolInt
    tarifAValue: Currency
    tarifBValue: Currency
    tarifAStart: Time
    tarifAStop: Time
    tarifBStart: Time
    tarifBStop: Time

    # --- Timer ---
    timerType: int
    timeZone: TimeZone
    systemTime: DateTime
    timeMsg: FrozenBoolInt

    # --- Limits ---
    timeLimitS: BoolInt
    energyLimitS: BoolInt
    moneyLimitS: BoolInt
    evseEnabled: BoolInt
    suspendErrors: int
    suspendLimits: BoolInt
    oneCharge: BoolInt
    delayedLimit: int
    timeLimit: int = Field(frozen=True)
    energyLimit: int = Field(frozen=True)
    moneyLimit: int = Field(frozen=True)

    # --- Schedule 1 ---
    sh1Enabled: BoolInt
    sh1Start: Time
    sh1Stop: Time
    sh1CurrentEnable: BoolInt
    sh1CurrentValue: int = Field(frozen=True)
    sh1EnergyEnable: BoolInt
    sh1EnergyValue: int = Field(frozen=True)

    # --- Schedule 2 ---
    sh2Enabled: BoolInt
    sh2Start: Time
    sh2Stop: Time
    sh2CurrentEnable: BoolInt
    sh2CurrentValue: int = Field(frozen=True)
    sh2EnergyEnable: BoolInt
    sh2EnergyValue: int = Field(frozen=True)

    # --- Energy totals (read-only) ---
    totalEnergy: float = Field(frozen=True)
    sessionTime: int = Field(frozen=True)
    sessionEnergy: float = Field(frozen=True)
    sessionMoney: float = Field(frozen=True)
    sessionStarted: FrozenBoolInt

    # --- Independent meters (read-only) ---
    IEM1: float = Field(frozen=True)
    IEM2: float = Field(frozen=True)
    IEM1_money: float = Field(frozen=True)
    IEM2_money: float = Field(frozen=True)

    # --- Measurements (read-only) ---
    curMeas1: int = Field(frozen=True)
    curMeas2: int = Field(frozen=True)
    curMeas3: int = Field(frozen=True)
    voltMeas1: int = Field(frozen=True)
    voltMeas2: int = Field(frozen=True)
    voltMeas3: int = Field(frozen=True)
    powerMeas: int = Field(frozen=True)
    temperature1: int = Field(frozen=True)
    temperature2: int = Field(frozen=True)
    leakValue: int = Field(frozen=True)
    leakValueH: int = Field(frozen=True)
    vBat: float = Field(frozen=True)
    adapter: int = Field(frozen=True)

    # --- Network (from /init) ---
    ssidNameAP: str = Field(json_schema_extra={"endpoint": CONFIG_AP_PATH})
    ssidPasswordAP: str = Field(json_schema_extra={"endpoint": CONFIG_AP_PATH})
    ssidName: str = Field(json_schema_extra={"endpoint": CONFIG_PATH})
    ssidPassword: str = Field(json_schema_extra={"endpoint": CONFIG_PATH})
    httpUsername: str = Field(json_schema_extra={"endpoint": CONFIG_HTTP_PATH})
    httpPassword: str = Field(json_schema_extra={"endpoint": CONFIG_HTTP_PATH})
    WifiMode: int = Field(json_schema_extra={"endpoint": CONFIG_PATH})
    ESP_MAC: str = Field(frozen=True)
    mac_bind: int = Field(json_schema_extra={"endpoint": CONFIG_PATH})
    STA_MAC: str = Field(frozen=True, json_schema_extra={"endpoint": CONFIG_PATH})

    # --- Confirmation fields (write-only, not returned by device) ---
    ssidPasswordAPConf: str = Field(default="", json_schema_extra={"endpoint": CONFIG_AP_PATH})
    httpPasswordConf: str = Field(default="", json_schema_extra={"endpoint": CONFIG_HTTP_PATH})
    ssidPasswordConf: str = Field(default="", json_schema_extra={"endpoint": CONFIG_PATH})

    # --- Network (from /main, read-only) ---
    scanComplete: FrozenBoolInt
    ocppconnected: FrozenBoolInt
    ocppEnabled: BoolInt
    ocppOfflineAva: BoolInt
    STA_IP_Addres: str = Field(frozen=True)  # device typo, preserved for compatibility
    RSSI: int = Field(frozen=True)
    logReady: Annotated[FrozenBoolInt, Field(default=False)]  # missing from response when not true

    # --- Other ---
    lang: int

    # --- Validation ---
    validators: ClassVar[list[Validator[Self]]] = [
        CurrentRestraintValidator(),
        PasswordLengthValidator("ssidPasswordAP"),
        PasswordLengthValidator("ssidPassword"),
        HttpAuthValidator(),
    ]


class Version_01_01(Version_01):
    """Document for Firmware 01.01"""
    pass


Document = Version_01_01
