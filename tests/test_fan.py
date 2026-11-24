"""Tests for the Vallox Modbus fan."""

from unittest.mock import MagicMock, call

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from vallox_modbus import (
    Profile,
    SystemMode,
    ValloxConnectionError,
    ValloxInvalidInputError,
    ValloxPartialWriteError,
)

from custom_components.vallox_modbus.const import DOMAIN
from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    NotValidPresetModeError,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import ENTRY_ID, settings_report

ENTITY_ID = "fan.vallox"

pytestmark = pytest.mark.usefixtures("init_integration")


async def _refresh(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Refresh both coordinators after changing the mocked device."""
    await entry.runtime_data.readings.async_refresh()
    await entry.runtime_data.settings.async_refresh()
    await hass.async_block_till_done()


async def _call(hass: HomeAssistant, service: str, **data: object) -> None:
    """Call a fan service on the Vallox fan."""
    await hass.services.async_call(
        FAN_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID, **data}, blocking=True
    )


async def test_state(hass: HomeAssistant, entity_registry: er.EntityRegistry) -> None:
    """Test the fan reports power, profile and the profile's fan speed."""
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PRESET_MODE] == "home"
    # Extra is shown, but its profile change is not validated on hardware.
    assert state.attributes[ATTR_PRESET_MODES] == [
        "home",
        "away",
        "boost",
        "fireplace",
        "auto",
    ]
    assert state.attributes[ATTR_PERCENTAGE] == 60
    assert state.attributes["fan_speed_home"] == 60
    assert state.attributes["fan_speed_away"] == 30
    assert state.attributes["fan_speed_boost"] == 90

    # The core vallox fan uses the bare device id as unique ID.
    assert entity_registry.async_get(ENTITY_ID).unique_id == ENTRY_ID


@pytest.mark.parametrize(
    ("profile", "preset_mode", "percentage"),
    [
        (Profile.AWAY, "away", 30),
        (Profile.BOOST, "boost", 90),
        (Profile.FIREPLACE, "fireplace", None),
        (Profile.EXTRA, "extra", None),
        # Automatic has no fan speed setting.
        (Profile.AUTOMATIC, "auto", None),
        (None, None, None),
    ],
)
async def test_profiles(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_device: MagicMock,
    profile: Profile | None,
    preset_mode: str | None,
    percentage: int | None,
) -> None:
    """Test the preset and percentage of every profile."""
    mock_device.profile = profile
    await _refresh(hass, init_integration)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_PRESET_MODE] == preset_mode
    assert state.attributes[ATTR_PERCENTAGE] == percentage


async def test_state_off(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_device: MagicMock
) -> None:
    """Test the fan is off while the unit is switched off."""
    mock_device.runtime.system_mode = SystemMode.OFF
    await _refresh(hass, init_integration)
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    mock_device.runtime.system_mode = None
    await _refresh(hass, init_integration)
    assert hass.states.get(ENTITY_ID).state == "unknown"


async def test_settings_unavailable(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_device: MagicMock
) -> None:
    """Test the percentage is unknown while the speed settings failed."""
    mock_device.async_update_settings.return_value = settings_report(
        settings=ValloxConnectionError("timeout")
    )
    await _refresh(hass, init_integration)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] is None
    assert state.attributes["fan_speed_home"] is None


async def test_turn_on_and_off(hass: HomeAssistant, mock_device: MagicMock) -> None:
    """Test switching the unit on and off."""
    await _call(hass, SERVICE_TURN_OFF)
    mock_device.async_set_power.assert_awaited_once_with(False)

    mock_device.async_set_power.reset_mock()
    await _call(hass, SERVICE_TURN_ON)
    mock_device.async_set_power.assert_awaited_once_with(True)


async def test_turn_on_with_percentage_and_preset(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test the speed is set first, then the preset, then the power."""
    await _call(hass, SERVICE_TURN_ON, percentage=70, preset_mode="boost")

    writes = [c for c in mock_device.mock_calls if c[0].startswith("async_set_")]
    assert writes == [
        call.async_set_boost_fan_speed(70),
        call.async_set_profile(Profile.BOOST),
        call.async_set_power(True),
    ]


async def test_turn_on_with_preset_without_speed(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test a preset without a speed setting fails before anything is written."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await _call(hass, SERVICE_TURN_ON, percentage=70, preset_mode="fireplace")

    assert exc_info.value.translation_key == "preset_without_fan_speed"
    mock_device.async_set_profile.assert_not_awaited()
    mock_device.async_set_power.assert_not_awaited()


async def test_turn_on_with_extra_preset(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test the Extra preset is rejected before anything is written."""
    with pytest.raises(NotValidPresetModeError):
        await _call(hass, SERVICE_TURN_ON, preset_mode="extra")

    writes = [c for c in mock_device.mock_calls if c[0].startswith("async_set_")]
    assert writes == []


async def test_turn_on_with_zero_percentage(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test turning on with 0 % switches the unit off."""
    await _call(hass, SERVICE_TURN_ON, percentage=0)
    mock_device.async_set_power.assert_awaited_once_with(False)


@pytest.mark.parametrize(
    ("preset_mode", "profile"),
    [
        ("home", Profile.HOME),
        ("away", Profile.AWAY),
        ("boost", Profile.BOOST),
        ("fireplace", Profile.FIREPLACE),
        ("auto", Profile.AUTOMATIC),
    ],
)
async def test_set_preset_mode(
    hass: HomeAssistant,
    mock_device: MagicMock,
    preset_mode: str,
    profile: Profile,
) -> None:
    """Test selecting a preset changes the profile and refreshes."""
    mock_device.async_update_readings.reset_mock()
    await _call(hass, SERVICE_SET_PRESET_MODE, preset_mode=preset_mode)

    mock_device.async_set_profile.assert_awaited_once_with(profile)
    mock_device.async_update_readings.assert_awaited()


async def test_set_extra_preset_mode(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test the Extra preset is not written, because it is not validated."""
    with pytest.raises(NotValidPresetModeError):
        await _call(hass, SERVICE_SET_PRESET_MODE, preset_mode="extra")

    mock_device.async_set_profile.assert_not_awaited()


@pytest.mark.parametrize(
    ("profile", "setter"),
    [
        (Profile.HOME, "async_set_home_fan_speed"),
        (Profile.AWAY, "async_set_away_fan_speed"),
        (Profile.BOOST, "async_set_boost_fan_speed"),
    ],
)
async def test_set_percentage(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_device: MagicMock,
    profile: Profile,
    setter: str,
) -> None:
    """Test the percentage sets the active profile's fan speed."""
    mock_device.profile = profile
    await _refresh(hass, init_integration)
    mock_device.async_update_settings.reset_mock()

    await _call(hass, SERVICE_SET_PERCENTAGE, percentage=70)

    getattr(mock_device, setter).assert_awaited_once_with(70)
    mock_device.async_update_settings.assert_awaited()


async def test_set_percentage_zero(hass: HomeAssistant, mock_device: MagicMock) -> None:
    """Test 0 % switches the unit off."""
    await _call(hass, SERVICE_SET_PERCENTAGE, percentage=0)
    mock_device.async_set_power.assert_awaited_once_with(False)
    mock_device.async_set_home_fan_speed.assert_not_awaited()


@pytest.mark.parametrize(
    ("profile", "preset_mode"),
    [(Profile.FIREPLACE, "fireplace"), (Profile.AUTOMATIC, "auto")],
)
async def test_set_percentage_without_speed_setting(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_device: MagicMock,
    profile: Profile,
    preset_mode: str,
) -> None:
    """Test profiles without a fan speed setting reject a percentage."""
    mock_device.profile = profile
    await _refresh(hass, init_integration)

    with pytest.raises(ServiceValidationError) as exc_info:
        await _call(hass, SERVICE_SET_PERCENTAGE, percentage=70)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_placeholders == {"preset_mode": preset_mode}


@pytest.mark.parametrize(
    ("error", "expected", "translation_key"),
    [
        (ValloxInvalidInputError("bad"), ServiceValidationError, "invalid_input"),
        (
            ValloxPartialWriteError("partial", completed=(4612,), failed=4613),
            HomeAssistantError,
            "partial_write",
        ),
        (ValloxConnectionError("timeout"), HomeAssistantError, "write_failed"),
    ],
)
async def test_write_errors(
    hass: HomeAssistant,
    mock_device: MagicMock,
    error: Exception,
    expected: type[Exception],
    translation_key: str,
) -> None:
    """Test write errors are translated and the state is refreshed anyway."""
    mock_device.async_set_profile.side_effect = error
    mock_device.async_update_readings.reset_mock()

    with pytest.raises(expected) as exc_info:
        await _call(hass, SERVICE_SET_PRESET_MODE, preset_mode="boost")

    assert exc_info.value.translation_key == translation_key
    mock_device.async_update_readings.assert_awaited()
