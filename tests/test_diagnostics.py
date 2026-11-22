"""Tests for the Vallox Modbus diagnostics."""

from unittest.mock import MagicMock

from modbus_connection import ModbusTimeoutError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from homeassistant.core import HomeAssistant

from .conftest import SERIAL_PORT


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test diagnostics contain raw registers and no serial port path."""
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )

    assert diagnostics["entry"]["data"] == {
        "device": "**REDACTED**",
        "baudrate": 19200,
        "parity": "E",
        "stopbits": 1,
        "unit_id": 1,
    }
    assert SERIAL_PORT not in str(diagnostics)
    assert diagnostics["coordinators"]["readings"] == {
        "last_update_success": True,
        "updated": ["inputs", "measurements", "runtime", "sensors", "timer_switches"],
        "failed": {},
    }
    assert diagnostics["profile"] == "HOME"
    assert diagnostics["raw_registers"] == {"holding": {"4353": 40, "4609": 0}}
    assert diagnostics["raw_registers_error"] is None


async def test_diagnostics_read_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test a failed raw read is reported instead of failing diagnostics."""
    mock_device.async_read_raw.side_effect = ModbusTimeoutError("no answer")

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )

    assert diagnostics["raw_registers"] is None
    assert "no answer" in diagnostics["raw_registers_error"]
