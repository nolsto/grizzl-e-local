from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Document(BaseModel):
    """Flat model mirroring the device's main.json document structure.

    Fields are kept as their native device types (int, float, str).
    Business logic and type coercion belong in the client/managers layers.
    """

    model_config = ConfigDict(extra="ignore")

    # --- Firmware ---
    verFWMain: str
    verFWWifi: str
    serialNumCPU: str
    serialNum: str
    fwCRC32: str
    verFWStatus: int

    # --- Status ---
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

    # --- Adaptive ---
    aiVoltage: int
    aiVoltageStart: int
    aiVoltageDrop: int
    aiPowerDrop: int
    aiMode: int = 0  # not in main.json but used by device

    # --- Power/ground ---
    SNflag: int
    ground: int
    groundCtrl: int

    # --- Tariffs ---
    tarif: int
    activeTarif: int
    tarifAEnable: int
    tarifBEnable: int
    tarifAValue: int
    tarifBValue: int
    tarifAStart: int
    tarifAStop: int
    tarifBStart: int
    tarifBStop: int

    # --- Timer ---
    timerType: int
    timeZone: int
    systemTime: int
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
    timeLimit: int
    energyLimit: int
    moneyLimit: int

    # --- Schedule 1 ---
    sh1Enabled: int
    sh1Start: int
    sh1Stop: int
    sh1CurrentEnable: int
    sh1CurrentValue: int
    sh1EnergyEnable: int
    sh1EnergyValue: int

    # --- Schedule 2 ---
    sh2Enabled: int
    sh2Start: int
    sh2Stop: int
    sh2CurrentEnable: int
    sh2CurrentValue: int
    sh2EnergyEnable: int
    sh2EnergyValue: int

    # --- Energy totals ---
    totalEnergy: float
    sessionTime: int
    sessionEnergy: float
    sessionMoney: float
    sessionStarted: int

    # --- Independent meters ---
    IEM1: float
    IEM2: float
    IEM1_money: float
    IEM2_money: float

    # --- Measurements ---
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

    # --- Network (from /init) ---
    ssidNameAP: str
    ssidPasswordAP: str
    ssidName: str
    ssidPassword: str
    httpUsername: str
    httpPassword: str
    WifiMode: int
    ESP_MAC: str
    mac_bind: int
    STA_MAC: str

    # --- Network (from /main) ---
    scanComplete: int
    ocppconnected: int
    ocppEnabled: int
    ocppOfflineAva: int
    STA_IP_Addres: str  # device typo, preserved for compatibility
    RSSI: int
    logReady: int

    # --- Other ---
    lang: int
