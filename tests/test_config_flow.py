"""Tests for the Vallox Modbus config flow."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

from modbus_connection import ModbusSerialParams
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from vallox_modbus import ValloxConnectionError, ValloxError

from custom_components.vallox_modbus.const import CONF_BAUDRATE, CONF_UNIT_ID, DOMAIN
from homeassistant.components.modbus.const import DATA_MODBUS_HUBS
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from .conftest import ENTRY_DATA, SERIAL_PORT, USER_INPUT


@pytest.fixture(autouse=True)
def mock_integration(mock_modbus: MagicMock) -> None:
    """Let created and reconfigured entries load with the mocked device."""


async def test_user_flow(hass: HomeAssistant, mock_probe: AsyncMock) -> None:
    """Test creating an entry after a successful probe."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Vallox"
    assert result["data"] == ENTRY_DATA
    mock_probe.temporary_unit.assert_called_once_with(
        hass,
        ModbusSerialParams(
            device=SERIAL_PORT, baudrate=19200, bytesize=8, parity="E", stopbits=1
        ),
        1,
    )
    mock_probe.assert_awaited_once()


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (ValloxConnectionError("timeout"), "cannot_connect"),
        (ValloxError("fan speed is not plausible"), "not_vallox"),
        (HomeAssistantError("in use"), "device_in_use"),
        (OSError("no such port"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_probe: AsyncMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test probe errors are shown and the flow recovers."""
    mock_probe.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_probe.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_probe: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the same unit on the same serial port is rejected before probing."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_BAUDRATE: "9600"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_probe.assert_not_awaited()


async def test_user_flow_other_unit_on_same_port(
    hass: HomeAssistant,
    mock_probe: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test another unit ID on the same serial port can be added."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_UNIT_ID: 2.0}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_UNIT_ID] == 2


async def test_user_flow_created_during_probe(
    hass: HomeAssistant,
    mock_probe: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an entry created by another flow during the probe aborts."""

    async def add_entry(*args: object) -> None:
        mock_config_entry.add_to_hass(hass)

    mock_probe.side_effect = add_entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure(
    hass: HomeAssistant,
    mock_probe: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test changing the baud rate of a loaded entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch.object(
        hass.config_entries, "async_unload", wraps=hass.config_entries.async_unload
    ) as unload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**USER_INPUT, CONF_BAUDRATE: "38400"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {**ENTRY_DATA, CONF_BAUDRATE: 38400}
    # The flow releases the serial port before probing; the reload unloads again.
    assert unload.await_args_list[0] == call(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_reconfigure_error_restores_entry(
    hass: HomeAssistant,
    mock_probe: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a failed probe sets the entry up again with the old settings."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    mock_probe.side_effect = ValloxConnectionError("timeout")
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_BAUDRATE: "38400"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert mock_config_entry.data == ENTRY_DATA
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_reconfigure_unload_fails(
    hass: HomeAssistant,
    mock_probe: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an entry that cannot be unloaded is not probed."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    with patch.object(
        hass.config_entries, "async_unload", AsyncMock(return_value=False)
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
    mock_probe.assert_not_awaited()


async def test_reconfigure_not_loaded(
    hass: HomeAssistant,
    mock_probe: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring an entry that is not loaded."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_UNIT_ID: 3.0}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_UNIT_ID] == 3


async def test_reconfigure_to_existing_unit(
    hass: HomeAssistant,
    mock_probe: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring onto a unit another entry uses is rejected."""
    mock_config_entry.add_to_hass(hass)
    other = MockConfigEntry(
        domain=DOMAIN,
        title="Vallox",
        data={**ENTRY_DATA, CONF_DEVICE: "/dev/ttyUSB1"},
    )
    other.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_DEVICE: "/dev/ttyUSB1"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_probe.assert_not_awaited()


async def test_user_flow_yaml_hub_on_port(
    hass: HomeAssistant, mock_probe: AsyncMock, yaml_hub: dict[str, Any]
) -> None:
    """Test a serial port used by a YAML modbus hub is rejected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "yaml_hub_in_use"}
    assert result["description_placeholders"] == {"hub": "vallox_yaml"}
    mock_probe.assert_not_awaited()


async def test_reconfigure_yaml_hub_on_port(
    hass: HomeAssistant,
    mock_probe: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring onto a port used by a YAML hub keeps the entry loaded."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    hass.data.setdefault(DATA_MODBUS_HUBS, {})["vallox_yaml"] = SimpleNamespace(
        endpoint=("serial", "/dev/ttyUSB1")
    )

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_DEVICE: "/dev/ttyUSB1"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "yaml_hub_in_use"}
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_probe.assert_not_awaited()
