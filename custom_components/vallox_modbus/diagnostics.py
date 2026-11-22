"""Diagnostics for the Vallox Modbus integration."""

from typing import Any

from modbus_connection import ModbusError

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant

from .const import READINGS_COMPONENTS, SETTINGS_COMPONENTS
from .coordinator import ValloxConfigEntry, ValloxCoordinator

# A serial-by-id path contains the adapter's serial number.
TO_REDACT = {CONF_DEVICE}


def _coordinator_diagnostics(coordinator: ValloxCoordinator) -> dict[str, Any]:
    """Return the outcome of a coordinator's last poll."""
    report = coordinator.data
    return {
        "last_update_success": coordinator.last_update_success,
        "updated": sorted(report.updated) if report else [],
        "failed": {name: repr(err) for name, err in report.failed.items()}
        if report
        else {},
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ValloxConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    The raw register values are read afresh from the unit, so they show what
    the unit reports independently of the integration's decoding.
    """
    runtime = entry.runtime_data
    device = runtime.device
    raw: dict[str, Any] | None = None
    raw_error: str | None = None
    try:
        raw = await device.async_read_raw(READINGS_COMPONENTS + SETTINGS_COMPONENTS)
    except ModbusError as err:
        raw_error = repr(err)

    profile = device.profile
    return {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
        },
        "coordinators": {
            "readings": _coordinator_diagnostics(runtime.readings),
            "settings": _coordinator_diagnostics(runtime.settings),
        },
        "profile": profile.name if profile is not None else None,
        "remaining_profile_duration": device.remaining_profile_duration,
        "raw_registers": raw,
        "raw_registers_error": raw_error,
    }
