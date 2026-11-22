"""Tests for setting up and unloading the Vallox Modbus integration."""

from typing import Any
from unittest.mock import MagicMock

from modbus_connection import ModbusConnectionError, ModbusSerialParams
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vallox_modbus.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .conftest import ENTRY_ID, SERIAL_PORT, readings_report


async def test_setup_and_unload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_modbus: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the entry gets its unit from the modbus integration and unloads."""
    assert init_integration.state is ConfigEntryState.LOADED
    mock_modbus.assert_called_once_with(
        hass,
        init_integration,
        ModbusSerialParams(
            device=SERIAL_PORT, baudrate=19200, bytesize=8, parity="E", stopbits=1
        ),
        1,
    )

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, ENTRY_ID), ENTRY_ID
    )
    assert device is not None
    assert device.manufacturer == "Vallox"
    assert device.name == "Vallox"

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_setup_device_in_use(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus: MagicMock,
) -> None:
    """Test a serial port in use with other settings fails permanently."""
    mock_modbus.side_effect = HomeAssistantError("in use")
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_retry_on_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus: MagicMock,
    mock_device: MagicMock,
) -> None:
    """Test an unreachable unit makes the setup retry."""
    mock_device.async_update_readings.side_effect = ModbusConnectionError("no port")
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retry_when_nothing_refreshed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus: MagicMock,
    mock_device: MagicMock,
) -> None:
    """Test a poll where every component failed makes the setup retry."""
    error = ModbusConnectionError("no answer")
    mock_device.async_update_readings.return_value = readings_report(
        measurements=error,
        runtime=error,
        inputs=error,
        sensors=error,
        timer_switches=error,
    )
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_yaml_hub_on_port(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus: MagicMock,
    yaml_hub: dict[str, Any],
) -> None:
    """Test the entry does not share its serial port with a YAML modbus hub."""
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason == (
        'The serial port is used by the Modbus hub "vallox_yaml" configured in '
        "YAML. Disable that hub, then reload this entry"
    )
    mock_modbus.assert_not_called()
