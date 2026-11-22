"""Tests for the Vallox Modbus coordinators."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusTimeoutError
from modbus_connection.model import UpdateReport
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.vallox_modbus.const import (
    READINGS_SCAN_INTERVAL,
    SETTINGS_SCAN_INTERVAL,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import readings_report, settings_report


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, interval: timedelta
) -> None:
    """Advance time by one poll interval."""
    freezer.tick(interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_partial_failure_marks_component_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_device: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed component makes only its entities unavailable."""
    assert hass.states.get("sensor.vallox_profile_duration").state != (
        STATE_UNAVAILABLE
    )

    mock_device.async_update_readings.return_value = readings_report(
        timer_switches=ModbusTimeoutError("no answer")
    )
    await _tick(hass, freezer, READINGS_SCAN_INTERVAL)

    assert hass.states.get("sensor.vallox_profile_duration").state == (
        STATE_UNAVAILABLE
    )
    assert hass.states.get("sensor.vallox_extract_air").state == "21.37"
    assert "timer_switches failed to refresh and is unavailable" in caplog.text

    mock_device.async_update_readings.return_value = readings_report()
    await _tick(hass, freezer, READINGS_SCAN_INTERVAL)

    assert hass.states.get("sensor.vallox_profile_duration").state != (
        STATE_UNAVAILABLE
    )
    assert "timer_switches is available again" in caplog.text


async def test_poll_error_marks_entities_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test a failed poll makes the coordinator's entities unavailable."""
    mock_device.async_update_readings.side_effect = ModbusTimeoutError("no answer")
    await _tick(hass, freezer, READINGS_SCAN_INTERVAL)

    assert hass.states.get("sensor.vallox_extract_air").state == STATE_UNAVAILABLE
    assert hass.states.get("fan.vallox").state == STATE_UNAVAILABLE
    # The settings coordinator is independent.
    assert hass.states.get("number.vallox_supply_air_temperature_home").state == (
        "13.0"
    )

    mock_device.async_update_readings.side_effect = None
    await _tick(hass, freezer, READINGS_SCAN_INTERVAL)

    assert hass.states.get("sensor.vallox_extract_air").state == "21.37"


async def test_empty_report_marks_entities_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test a poll that refreshed nothing fails the update."""
    mock_device.async_update_settings.return_value = UpdateReport()
    await _tick(hass, freezer, SETTINGS_SCAN_INTERVAL)

    assert hass.states.get("number.vallox_supply_air_temperature_home").state == (
        STATE_UNAVAILABLE
    )


async def test_settings_poll_interval(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test readings poll every minute and settings every ten minutes."""
    mock_device.async_update_readings.reset_mock()
    mock_device.async_update_settings.reset_mock()

    await _tick(hass, freezer, READINGS_SCAN_INTERVAL)
    assert mock_device.async_update_readings.await_count == 1
    assert mock_device.async_update_settings.await_count == 0

    mock_device.async_update_settings.return_value = settings_report()
    await _tick(hass, freezer, SETTINGS_SCAN_INTERVAL - READINGS_SCAN_INTERVAL)
    assert mock_device.async_update_settings.await_count == 1


async def test_coordinator_for_rejects_mixed_components(
    init_integration: MockConfigEntry,
) -> None:
    """Test an entity cannot read components of both coordinators."""
    runtime = init_integration.runtime_data
    assert runtime.coordinator_for(("settings", "configuration")) is runtime.settings
    assert runtime.coordinator_for(("runtime",)) is runtime.readings
    with pytest.raises(ValueError, match="span both coordinators"):
        runtime.coordinator_for(("runtime", "settings"))
