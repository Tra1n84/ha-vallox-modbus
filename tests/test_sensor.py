"""Tests for the Vallox Modbus sensors."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from vallox_modbus import HeatExchangerState, Profile, SystemMode

from homeassistant.const import STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import ENTRY_ID


async def _refresh(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Refresh both coordinators after changing the mocked device."""
    await entry.runtime_data.readings.async_refresh()
    await entry.runtime_data.settings.async_refresh()
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
@pytest.mark.parametrize(
    ("entity_id", "state"),
    [
        ("sensor.vallox_extract_air", "21.37"),
        ("sensor.vallox_exhaust_air", "5.52"),
        ("sensor.vallox_outdoor_air", "2.25"),
        ("sensor.vallox_supply_air", "19.5"),
        ("sensor.vallox_supply_cell_air", "18.04"),
        ("sensor.vallox_optional_air", STATE_UNKNOWN),
        ("sensor.vallox_humidity", "45"),
        ("sensor.vallox_carbon_dioxide", STATE_UNKNOWN),
        ("sensor.vallox_current_profile", "home"),
        ("sensor.vallox_fan_speed", "40"),
        ("sensor.vallox_extract_fan_speed", "1510"),
        ("sensor.vallox_supply_fan_speed", "1450"),
        ("sensor.vallox_remaining_time_for_filter", "2026-11-28T21:00:00+00:00"),
        ("sensor.vallox_cell_state", "heat_recovery"),
        ("sensor.vallox_profile_duration", STATE_UNKNOWN),
        ("sensor.vallox_filter_time_remaining", "120"),
    ],
)
async def test_states(hass: HomeAssistant, entity_id: str, state: str) -> None:
    """Test the sensor states."""
    assert hass.states.get(entity_id).state == state


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("entity_id", "unique_key"),
    [
        ("sensor.vallox_extract_air", "extract_air"),
        ("sensor.vallox_optional_air", "optional_air"),
        ("sensor.vallox_carbon_dioxide", "co2"),
        ("sensor.vallox_extract_fan_speed", "extract_fan_speed"),
        ("sensor.vallox_supply_fan_speed", "supply_fan_speed"),
    ],
)
async def test_unique_ids_follow_core(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_id: str,
    unique_key: str,
) -> None:
    """Test unique IDs use the core vallox keys and diagnostic category."""
    entry = entity_registry.async_get(entity_id)
    assert entry.unique_id == f"{ENTRY_ID}-{unique_key}"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.vallox_optional_air",
        "sensor.vallox_carbon_dioxide",
        "sensor.vallox_extract_fan_speed",
        "sensor.vallox_supply_fan_speed",
    ],
)
async def test_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entity_id: str
) -> None:
    """Test the sensors core vallox disables by default are disabled too."""
    assert (
        entity_registry.async_get(entity_id).disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )
    assert hass.states.get(entity_id) is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_fan_speeds_are_zero_while_off(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_device: MagicMock
) -> None:
    """Test the unit's last fan speeds are hidden while it is off."""
    mock_device.runtime.system_mode = SystemMode.OFF
    await _refresh(hass, init_integration)

    assert hass.states.get("sensor.vallox_fan_speed").state == "0"
    assert hass.states.get("sensor.vallox_extract_fan_speed").state == "0"

    mock_device.runtime.system_mode = None
    await _refresh(hass, init_integration)
    assert hass.states.get("sensor.vallox_fan_speed").state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("profile", "state"),
    [
        (Profile.AWAY, "away"),
        (Profile.AUTOMATIC, "auto"),
        (Profile.BOOST, "boost"),
        (Profile.FIREPLACE, "fireplace"),
        (Profile.EXTRA, "extra"),
        (None, STATE_UNKNOWN),
    ],
)
async def test_current_profile(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_device: MagicMock,
    profile: Profile | None,
    state: str,
) -> None:
    """Test every profile the unit reports, including Automatic."""
    mock_device.profile = profile
    await _refresh(hass, init_integration)
    assert hass.states.get("sensor.vallox_current_profile").state == state


async def test_profile_duration_and_cell_state(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_device: MagicMock
) -> None:
    """Test the remaining profile time and the heat exchanger state."""
    mock_device.remaining_profile_duration = 25
    mock_device.runtime.heat_exchanger_state = HeatExchangerState.BYPASS
    await _refresh(hass, init_integration)

    assert hass.states.get("sensor.vallox_profile_duration").state == "25"
    assert hass.states.get("sensor.vallox_cell_state").state == "bypass"


async def test_no_filter_change_date(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_device: MagicMock
) -> None:
    """Test the filter due date is unknown without a stored change date."""
    mock_device.next_filter_change_date = None
    await _refresh(hass, init_integration)

    assert hass.states.get("sensor.vallox_remaining_time_for_filter").state == (
        STATE_UNKNOWN
    )
