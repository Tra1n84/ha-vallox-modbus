"""The Vallox Modbus integration."""

from vallox_modbus import ValloxDevice

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_DEVICE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError

from .const import (
    CONF_UNIT_ID,
    DOMAIN,
    READINGS_SCAN_INTERVAL,
    SETTINGS_RETRY_INTERVAL,
    SETTINGS_SCAN_INTERVAL,
)
from .coordinator import ValloxConfigEntry, ValloxCoordinator, ValloxRuntimeData
from .helpers import async_find_yaml_hub, create_modbus_params

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.FAN,
    Platform.NUMBER,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ValloxConfigEntry) -> bool:
    """Set up a Vallox unit from a config entry."""
    # The modbus dependency has set up its YAML hubs before this entry.
    if hub := await async_find_yaml_hub(hass, entry.data[CONF_DEVICE]):
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="yaml_hub_in_use",
            translation_placeholders={"hub": hub},
        )
    try:
        unit = async_get_unit(
            hass, entry, create_modbus_params(entry.data), entry.data[CONF_UNIT_ID]
        )
    except HomeAssistantError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="connect_failed",
            translation_placeholders={"error": str(err)},
        ) from err

    device = ValloxDevice(unit)
    readings = ValloxCoordinator(
        hass,
        entry,
        device,
        device.async_update_readings,
        READINGS_SCAN_INTERVAL,
        "readings",
    )
    settings = ValloxCoordinator(
        hass,
        entry,
        device,
        device.async_update_settings,
        SETTINGS_SCAN_INTERVAL,
        "settings",
        SETTINGS_RETRY_INTERVAL,
    )
    entry.runtime_data = ValloxRuntimeData(device, readings, settings)

    await readings.async_config_entry_first_refresh()
    await settings.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ValloxConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
