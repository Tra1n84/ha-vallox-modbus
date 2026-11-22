"""Tests for the Vallox Modbus number entities."""

from unittest.mock import MagicMock

import pytest
from vallox_modbus import ValloxConnectionError, ValloxInvalidInputError

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import ENTRY_ID

pytestmark = pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "init_integration"
)

NUMBERS = [
    # entity_id, unique key, state, setter, value written, value passed
    (
        "number.vallox_supply_air_temperature_home",
        "supply_air_target_home",
        "13.0",
        "async_set_home_air_temperature_target",
        14.0,
        14.0,
    ),
    (
        "number.vallox_supply_air_temperature_away",
        "supply_air_target_away",
        "15.0",
        "async_set_away_air_temperature_target",
        16.0,
        16.0,
    ),
    (
        "number.vallox_supply_air_temperature_boost",
        "supply_air_target_boost",
        "15.0",
        "async_set_boost_air_temperature_target",
        17.0,
        17.0,
    ),
    (
        "number.vallox_supply_air_temperature_extra",
        "supply_air_target_extra",
        "15.0",
        "async_set_extra_air_temperature_target",
        18.0,
        18.0,
    ),
    (
        "number.vallox_fan_speed_home",
        "fan_speed_home",
        "60",
        "async_set_home_fan_speed",
        65,
        65,
    ),
    (
        "number.vallox_fan_speed_away",
        "fan_speed_away",
        "30",
        "async_set_away_fan_speed",
        35,
        35,
    ),
    (
        "number.vallox_fan_speed_boost",
        "fan_speed_boost",
        "90",
        "async_set_boost_fan_speed",
        95,
        95,
    ),
    (
        "number.vallox_extract_fan_speed_extra",
        "extra_extract_fan",
        "50",
        "async_set_extra_extract_fan",
        55,
        55,
    ),
    (
        "number.vallox_supply_fan_speed_extra",
        "extra_supply_fan",
        "50",
        "async_set_extra_supply_fan",
        45,
        45,
    ),
    (
        "number.vallox_boost_duration",
        "boost_duration",
        "30",
        "async_set_boost_duration",
        45,
        45,
    ),
    (
        "number.vallox_fireplace_duration",
        "fireplace_duration",
        "15",
        "async_set_fireplace_duration",
        20,
        20,
    ),
    (
        "number.vallox_extra_duration",
        "extra_duration",
        "10",
        "async_set_extra_duration",
        25,
        25,
    ),
]


@pytest.mark.parametrize(
    ("entity_id", "key", "state", "setter", "value", "expected"), NUMBERS
)
async def test_numbers(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    entity_id: str,
    key: str,
    state: str,
    setter: str,
    value: float,
    expected: float,
) -> None:
    """Test each number reads its setting and writes it through the library."""
    assert hass.states.get(entity_id).state == state
    entry = entity_registry.async_get(entity_id)
    assert entry.unique_id == f"{ENTRY_ID}-{key}"
    assert entry.entity_category is EntityCategory.CONFIG

    mock_device.async_update_settings.reset_mock()
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )

    getattr(mock_device, setter).assert_awaited_once_with(expected)
    passed = getattr(mock_device, setter).await_args.args[0]
    assert type(passed) is type(expected)
    mock_device.async_update_settings.assert_awaited()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ValloxInvalidInputError("out of range"), ServiceValidationError),
        (ValloxConnectionError("timeout"), HomeAssistantError),
    ],
)
async def test_write_errors(
    hass: HomeAssistant,
    mock_device: MagicMock,
    error: Exception,
    expected: type[Exception],
) -> None:
    """Test write errors are translated."""
    mock_device.async_set_home_fan_speed.side_effect = error

    with pytest.raises(expected):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.vallox_fan_speed_home", ATTR_VALUE: 50},
            blocking=True,
        )
