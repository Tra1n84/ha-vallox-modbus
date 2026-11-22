"""Tests for the Vallox Modbus binary sensors."""

from unittest.mock import MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant


async def test_states(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_device: MagicMock
) -> None:
    """Test the defrosting and fault states."""
    assert hass.states.get("binary_sensor.vallox_defrosting").state == STATE_OFF
    assert hass.states.get("binary_sensor.vallox_fault").state == STATE_OFF

    mock_device.runtime.defrosting = True
    mock_device.runtime.fault = True
    await init_integration.runtime_data.readings.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.vallox_defrosting").state == STATE_ON
    assert hass.states.get("binary_sensor.vallox_fault").state == STATE_ON
