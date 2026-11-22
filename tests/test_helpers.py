"""Tests for the Vallox Modbus helpers."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from custom_components.vallox_modbus.helpers import async_find_yaml_hub
from homeassistant.core import HomeAssistant

from .conftest import SERIAL_PORT


async def test_find_yaml_hub_same_path(
    hass: HomeAssistant, yaml_hub: dict[str, Any]
) -> None:
    """Test a YAML hub on the same serial port path is found."""
    assert await async_find_yaml_hub(hass, SERIAL_PORT) == "vallox_yaml"


async def test_find_yaml_hub_through_symlink(
    hass: HomeAssistant, yaml_hub: dict[str, Any], tmp_path: Path
) -> None:
    """Test a by-id symlink and the device it points to are the same port."""
    device = tmp_path / "ttyUSB0"
    device.touch()
    by_id = tmp_path / "usb-adapter-port0"
    by_id.symlink_to(device)
    yaml_hub["vallox_yaml"] = SimpleNamespace(endpoint=("serial", str(device)))

    assert await async_find_yaml_hub(hass, str(by_id)) == "vallox_yaml"


async def test_find_yaml_hub_ignores_other_hubs(
    hass: HomeAssistant, yaml_hub: dict[str, Any]
) -> None:
    """Test hubs on other ports, network hubs and unknown shapes are ignored."""
    yaml_hub.clear()
    yaml_hub["other_port"] = SimpleNamespace(endpoint=("serial", "/dev/ttyUSB9"))
    yaml_hub["tcp"] = SimpleNamespace(endpoint=("tcp", "1.2.3.4", 502))
    yaml_hub["no_endpoint"] = SimpleNamespace()

    assert await async_find_yaml_hub(hass, SERIAL_PORT) is None


async def test_find_yaml_hub_without_hubs(hass: HomeAssistant) -> None:
    """Test no YAML modbus configuration means no conflict."""
    assert await async_find_yaml_hub(hass, SERIAL_PORT) is None
