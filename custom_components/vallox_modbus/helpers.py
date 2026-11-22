"""Connection helpers for the Vallox Modbus integration."""

from collections.abc import Mapping
import os
from typing import Any

from modbus_connection import ModbusSerialParams

from homeassistant.components.modbus.const import DATA_MODBUS_HUBS
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant

from .const import BYTESIZE, CONF_BAUDRATE, CONF_PARITY, CONF_STOPBITS


def create_modbus_params(data: Mapping[str, Any]) -> ModbusSerialParams:
    """Build Modbus RTU connection parameters from config entry data."""
    return ModbusSerialParams(
        device=data[CONF_DEVICE],
        baudrate=data[CONF_BAUDRATE],
        bytesize=BYTESIZE,
        parity=data[CONF_PARITY],
        stopbits=data[CONF_STOPBITS],
    )


async def async_find_yaml_hub(hass: HomeAssistant, device: str) -> str | None:
    """Return the name of a YAML Modbus hub that uses the same serial port.

    A hub configured under `modbus:` in YAML opens its own connection instead
    of sharing the one `async_get_unit` hands out, so Home Assistant does not
    detect the conflict. Two masters on one serial port garble each other's
    requests. The hubs are internal data of the modbus integration, so an
    unexpected shape is treated as no conflict.
    """
    ports: dict[str, str] = {}
    for name, hub in hass.data.get(DATA_MODBUS_HUBS, {}).items():
        endpoint = getattr(hub, "endpoint", None)
        if isinstance(endpoint, tuple) and len(endpoint) == 2:  # noqa: PLR2004
            transport, port = endpoint
            if transport == "serial" and isinstance(port, str):
                ports[name] = port
    if not ports:
        return None

    def find() -> str | None:
        # A /dev/serial/by-id path and /dev/ttyUSB0 can name the same port.
        target = os.path.realpath(device)
        for name, port in ports.items():
            if port == device or os.path.realpath(port) == target:
                return name
        return None

    return await hass.async_add_executor_job(find)
