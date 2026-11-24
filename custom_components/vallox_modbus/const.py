"""Constants for the Vallox Modbus integration."""

from datetime import timedelta
from typing import Final

from vallox_modbus import HeatExchangerState, Profile

DOMAIN: Final = "vallox_modbus"
DEFAULT_NAME: Final = "Vallox"
MANUFACTURER: Final = "Vallox"

CONF_BAUDRATE: Final = "baudrate"
CONF_PARITY: Final = "parity"
CONF_STOPBITS: Final = "stopbits"
CONF_UNIT_ID: Final = "unit_id"

# Vallox MV units speak Modbus RTU with 8 data bits. Baudrate, parity and stop
# bits are configurable on the unit (registers 20483 and 20484).
BYTESIZE: Final = 8
BAUDRATES: Final = (9600, 19200, 38400, 57600, 115200)
# Config flow option (translation keys must be lower case) -> stored parity.
PARITY_OPTIONS: Final = {"none": "N", "even": "E", "odd": "O"}
STOPBITS: Final = (1, 2)

DEFAULT_BAUDRATE: Final = 19200
DEFAULT_PARITY: Final = "E"
DEFAULT_STOPBITS: Final = 1
DEFAULT_UNIT_ID: Final = 1
MIN_UNIT_ID: Final = 1
MAX_UNIT_ID: Final = 247

READINGS_SCAN_INTERVAL: Final = timedelta(seconds=60)
SETTINGS_SCAN_INTERVAL: Final = timedelta(minutes=10)
# Retry failed settings sooner, so a single timeout does not leave the profile
# fan speeds unknown for a whole settings interval.
SETTINGS_RETRY_INTERVAL: Final = timedelta(seconds=60)

READINGS_COMPONENTS: Final = (
    "measurements",
    "runtime",
    "inputs",
    "sensors",
    "timer_switches",
)
SETTINGS_COMPONENTS: Final = ("settings", "configuration")

# Preset modes that can be selected on the fan, as in the core vallox
# integration. The profile change of every preset is validated on hardware,
# according to vallox-modbus docs/hardware-validation.md.
PRESET_MODE_TO_PROFILE: Final = {
    "home": Profile.HOME,
    "away": Profile.AWAY,
    "boost": Profile.BOOST,
    "fireplace": Profile.FIREPLACE,
    "extra": Profile.EXTRA,
    "auto": Profile.AUTOMATIC,
}

# Every profile is selectable, so the reverse lookup covers them all.
PROFILE_TO_PRESET_MODE: Final = {
    profile: preset for preset, profile in PRESET_MODE_TO_PROFILE.items()
}

CELL_STATE_TO_STR: Final = {
    HeatExchangerState.HEAT_RECOVERY: "heat_recovery",
    HeatExchangerState.COOL_RECOVERY: "cool_recovery",
    HeatExchangerState.BYPASS: "bypass",
    HeatExchangerState.DEFROSTING: "defrosting",
}
