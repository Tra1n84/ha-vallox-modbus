"""Fixtures for the Vallox Modbus tests.

The tests never touch a serial port: the integration's Modbus unit and the
`ValloxDevice` are mocks, so every write is a mock call.
"""

from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from modbus_connection.model import UpdateReport
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from vallox_modbus import (
    BasicProfile,
    HeatExchangerState,
    Profile,
    SystemMode,
    ValloxDevice,
)

from custom_components.vallox_modbus.const import (
    CONF_BAUDRATE,
    CONF_PARITY,
    CONF_STOPBITS,
    CONF_UNIT_ID,
    DOMAIN,
    READINGS_COMPONENTS,
    SETTINGS_COMPONENTS,
)
from homeassistant.components.modbus.const import DATA_MODBUS_HUBS
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

SERIAL_PORT = "/dev/serial/by-id/usb-1a86_USB2.0-Ser_-if00-port0"
ENTRY_ID = "01JZ8M2Q4T6Y9V3B5N7K1W0XAE"

ENTRY_DATA: dict[str, Any] = {
    CONF_DEVICE: SERIAL_PORT,
    CONF_BAUDRATE: 19200,
    CONF_PARITY: "E",
    CONF_STOPBITS: 1,
    CONF_UNIT_ID: 1,
}

# What the config flow form submits: selectors return strings and floats.
USER_INPUT: dict[str, Any] = {
    CONF_DEVICE: SERIAL_PORT,
    CONF_BAUDRATE: "19200",
    CONF_PARITY: "even",
    CONF_STOPBITS: "1",
    CONF_UNIT_ID: 1.0,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load the integration from custom_components."""


@pytest.fixture
def entity_registry_enabled_by_default() -> Generator[None]:
    """Create entities that are disabled by default as enabled."""
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        return_value=True,
        new_callable=PropertyMock,
    ):
        yield


def readings_report(**failed: Exception) -> UpdateReport:
    """Return a readings poll report, with the given components failed."""
    return UpdateReport(
        updated=set(READINGS_COMPONENTS) - failed.keys(), failed=dict(failed)
    )


def settings_report(**failed: Exception) -> UpdateReport:
    """Return a settings poll report, with the given components failed."""
    return UpdateReport(
        updated=set(SETTINGS_COMPONENTS) - failed.keys(), failed=dict(failed)
    )


def make_device() -> MagicMock:
    """Return a mocked ValloxDevice holding plausible decoded values."""
    device = MagicMock(spec=ValloxDevice)
    device.measurements = SimpleNamespace(
        fan_speed=40,
        extract_air_temperature=21.37,
        exhaust_air_temperature=5.52,
        outdoor_air_temperature=2.25,
        supply_cell_air_temperature=18.04,
        supply_air_temperature=19.5,
        humidity=45,
        co2=None,
        extract_fan_rpm=1510,
        supply_fan_rpm=1450,
    )
    device.runtime = SimpleNamespace(
        basic_profile=BasicProfile.HOME,
        system_mode=SystemMode.NORMAL,
        defrosting=False,
        fault=False,
        heat_exchanger_state=HeatExchangerState.HEAT_RECOVERY,
        filter_remaining=120,
    )
    device.sensors = SimpleNamespace(optional_temperature=None)
    device.settings = SimpleNamespace(
        home_fan_speed=60,
        away_fan_speed=30,
        boost_fan_speed=90,
        home_air_temperature_target=13.0,
        away_air_temperature_target=15.0,
        boost_air_temperature_target=15.0,
        boost_duration=30,
        fireplace_duration=15,
        filter_change_date=date(2026, 6, 1),
    )
    device.configuration = SimpleNamespace(
        extra_air_temperature_target=15.0,
        extra_extract_fan=50,
        extra_supply_fan=50,
        extra_duration=10,
        filter_change_interval=180,
    )
    device.profile = Profile.HOME
    device.remaining_profile_duration = None
    device.next_filter_change_date = date(2026, 11, 28)
    device.async_update_readings.return_value = readings_report()
    device.async_update_settings.return_value = settings_report()
    device.async_read_raw.return_value = {"holding": {4353: 40, 4609: 0}}
    return device


@pytest.fixture
def mock_device() -> MagicMock:
    """Return the mocked device used by the integration."""
    return make_device()


@pytest.fixture
def mock_modbus(mock_device: MagicMock) -> Generator[MagicMock]:
    """Hand the integration a mocked unit and the mocked device."""
    with (
        patch(
            "custom_components.vallox_modbus.async_get_unit", return_value=MagicMock()
        ) as get_unit,
        patch("custom_components.vallox_modbus.ValloxDevice", return_value=mock_device),
    ):
        yield get_unit


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Vallox Modbus config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Vallox",
        entry_id=ENTRY_ID,
        data=dict(ENTRY_DATA),
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus: MagicMock,
) -> MockConfigEntry:
    """Set up the integration with the mocked device."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry


@pytest.fixture
def mock_probe() -> Generator[AsyncMock]:
    """Mock the config flow's probe and its temporary Modbus unit."""
    unit = MagicMock()

    @asynccontextmanager
    async def temporary_unit(*args: Any) -> AsyncIterator[MagicMock]:
        yield unit

    temporary = MagicMock(side_effect=temporary_unit)
    with (
        patch(
            "custom_components.vallox_modbus.config_flow.async_get_temporary_unit",
            temporary,
        ),
        patch(
            "custom_components.vallox_modbus.config_flow.ValloxDevice.async_probe",
            new_callable=AsyncMock,
        ) as probe,
    ):
        probe.temporary_unit = temporary
        yield probe


@pytest.fixture
async def yaml_hub(hass: HomeAssistant) -> dict[str, Any]:
    """Register a YAML Modbus hub on the integration's serial port."""
    assert await async_setup_component(hass, "modbus", {})
    hubs = hass.data.setdefault(DATA_MODBUS_HUBS, {})
    hubs["vallox_yaml"] = SimpleNamespace(endpoint=("serial", SERIAL_PORT))
    return hubs
