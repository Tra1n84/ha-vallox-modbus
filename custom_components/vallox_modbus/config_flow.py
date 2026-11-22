"""Config flow for the Vallox Modbus integration."""

import logging
from typing import Any, override

import probatio
from vallox_modbus import ValloxConnectionError, ValloxDevice, ValloxError

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigEntryState, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SerialPortSelector,
)

from .const import (
    BAUDRATES,
    CONF_BAUDRATE,
    CONF_PARITY,
    CONF_STOPBITS,
    CONF_UNIT_ID,
    DEFAULT_BAUDRATE,
    DEFAULT_NAME,
    DEFAULT_PARITY,
    DEFAULT_STOPBITS,
    DEFAULT_UNIT_ID,
    DOMAIN,
    MAX_UNIT_ID,
    MIN_UNIT_ID,
    PARITY_OPTIONS,
    STOPBITS,
)
from .helpers import async_find_yaml_hub, create_modbus_params

_LOGGER = logging.getLogger(__name__)

_PARITY_TO_OPTION = {parity: option for option, parity in PARITY_OPTIONS.items()}

STEP_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_DEVICE): SerialPortSelector(),
        probatio.Required(CONF_BAUDRATE, default=str(DEFAULT_BAUDRATE)): SelectSelector(
            SelectSelectorConfig(
                options=[str(baudrate) for baudrate in BAUDRATES],
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        probatio.Required(
            CONF_PARITY, default=_PARITY_TO_OPTION[DEFAULT_PARITY]
        ): SelectSelector(
            SelectSelectorConfig(
                options=list(PARITY_OPTIONS),
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_PARITY,
            )
        ),
        probatio.Required(CONF_STOPBITS, default=str(DEFAULT_STOPBITS)): SelectSelector(
            SelectSelectorConfig(
                options=[str(stopbits) for stopbits in STOPBITS],
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): probatio.All(
            NumberSelector(
                NumberSelectorConfig(
                    min=MIN_UNIT_ID,
                    max=MAX_UNIT_ID,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            probatio.Coerce(int),
        ),
    }
)


def _normalize(user_input: dict[str, Any]) -> dict[str, Any]:
    """Convert selector values to the types stored in the config entry."""
    return {
        CONF_DEVICE: str(user_input[CONF_DEVICE]),
        CONF_BAUDRATE: int(user_input[CONF_BAUDRATE]),
        CONF_PARITY: PARITY_OPTIONS[user_input[CONF_PARITY]],
        CONF_STOPBITS: int(user_input[CONF_STOPBITS]),
        CONF_UNIT_ID: int(user_input[CONF_UNIT_ID]),
    }


def _suggested_values(data: dict[str, Any]) -> dict[str, Any]:
    """Convert stored config entry values back to selector values."""
    return {
        CONF_DEVICE: data[CONF_DEVICE],
        CONF_BAUDRATE: str(data[CONF_BAUDRATE]),
        CONF_PARITY: _PARITY_TO_OPTION[data[CONF_PARITY]],
        CONF_STOPBITS: str(data[CONF_STOPBITS]),
        CONF_UNIT_ID: data[CONF_UNIT_ID],
    }


def _bus_match(data: dict[str, Any]) -> dict[str, Any]:
    """Return the values that identify one unit on one serial bus."""
    return {CONF_DEVICE: data[CONF_DEVICE], CONF_UNIT_ID: data[CONF_UNIT_ID]}


class ValloxModbusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for a Vallox unit over Modbus RTU."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the serial port and Modbus unit."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            data = _normalize(user_input)
            self._async_abort_entries_match(_bus_match(data))
            if hub := await async_find_yaml_hub(self.hass, data[CONF_DEVICE]):
                errors["base"] = "yaml_hub_in_use"
                placeholders["hub"] = hub
            elif (error := await self._async_probe(data)) is not None:
                errors["base"] = error
            else:
                # Another flow can create a matching entry during the probe.
                self._async_abort_entries_match(_bus_match(data))
                return self.async_create_entry(title=DEFAULT_NAME, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_SCHEMA, _suggested_values(_normalize(user_input))
            )
            if user_input is not None
            else STEP_SCHEMA,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the serial settings or unit ID of an existing entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        suggested = _suggested_values(dict(entry.data))
        if user_input is not None:
            data = _normalize(user_input)
            suggested = _suggested_values(data)
            if _bus_match(data) != _bus_match(dict(entry.data)):
                self._async_abort_entries_match(_bus_match(data))

            # The loaded entry holds the serial port with its current settings.
            # Release it so the probe can open the port with the new settings.
            entry_was_loaded = entry.state is ConfigEntryState.LOADED
            if hub := await async_find_yaml_hub(self.hass, data[CONF_DEVICE]):
                errors["base"] = "yaml_hub_in_use"
                placeholders["hub"] = hub
            elif entry_was_loaded and not await self.hass.config_entries.async_unload(
                entry.entry_id
            ):
                errors["base"] = "unknown"
            elif (error := await self._async_probe(data)) is not None:
                errors["base"] = error
                if entry_was_loaded:
                    await self.hass.config_entries.async_setup(entry.entry_id)
            else:
                return self.async_update_reload_and_abort(entry, data_updates=data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(STEP_SCHEMA, suggested),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def _async_probe(self, data: dict[str, Any]) -> str | None:
        """Read the unit without writing and return an error key on failure."""
        try:
            async with async_get_temporary_unit(
                self.hass, create_modbus_params(data), data[CONF_UNIT_ID]
            ) as unit:
                await ValloxDevice.async_probe(unit)
        except ValloxConnectionError:
            _LOGGER.debug("Cannot connect to the Vallox unit", exc_info=True)
            return "cannot_connect"
        except ValloxError:
            _LOGGER.debug("Unit does not answer like a Vallox MV unit", exc_info=True)
            return "not_vallox"
        except HomeAssistantError:
            _LOGGER.debug("Serial port is in use", exc_info=True)
            return "device_in_use"
        except OSError:
            _LOGGER.debug("Cannot open the serial port", exc_info=True)
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return "unknown"
        return None
