"""Number platform for the Vallox Modbus integration.

Only settings whose writes are validated on hardware, according to
vallox-modbus docs/hardware-validation.md, are exposed.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

from vallox_modbus import ValloxDevice

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ValloxConfigEntry
from .entity import ValloxEntity, ValloxEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class ValloxNumberEntityDescription(NumberEntityDescription, ValloxEntityDescription):
    """Describes a Vallox number entity."""

    value_fn: Callable[[ValloxDevice], float | None]
    set_fn: Callable[[ValloxDevice, float], Awaitable[None]]


def _air_temperature_target(
    key: str,
    component: str,
    value_fn: Callable[[ValloxDevice], float | None],
    set_fn: Callable[[ValloxDevice, float], Awaitable[None]],
    *,
    enabled_default: bool = True,
) -> ValloxNumberEntityDescription:
    """Describe a supply air temperature target, as in core vallox."""
    return ValloxNumberEntityDescription(
        key=key,
        translation_key=key,
        components=(component,),
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=5.0,
        native_max_value=25.0,
        native_step=1.0,
        entity_registry_enabled_default=enabled_default,
        value_fn=value_fn,
        set_fn=set_fn,
    )


def _percent(
    key: str,
    component: str,
    value_fn: Callable[[ValloxDevice], float | None],
    set_fn: Callable[[ValloxDevice, int], Awaitable[None]],
    *,
    enabled_default: bool = True,
) -> ValloxNumberEntityDescription:
    """Describe a fan speed setting in percent."""
    return ValloxNumberEntityDescription(
        key=key,
        translation_key=key,
        components=(component,),
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        entity_registry_enabled_default=enabled_default,
        value_fn=value_fn,
        set_fn=lambda device, value: set_fn(device, int(value)),
    )


def _duration(
    key: str,
    component: str,
    value_fn: Callable[[ValloxDevice], float | None],
    set_fn: Callable[[ValloxDevice, int], Awaitable[None]],
) -> ValloxNumberEntityDescription:
    """Describe the configured duration of a timed profile."""
    return ValloxNumberEntityDescription(
        key=key,
        translation_key=key,
        components=(component,),
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=1,
        native_max_value=65535,
        native_step=1,
        mode=NumberMode.BOX,
        entity_registry_enabled_default=False,
        value_fn=value_fn,
        set_fn=lambda device, value: set_fn(device, int(value)),
    )


NUMBER_DESCRIPTIONS: tuple[ValloxNumberEntityDescription, ...] = (
    # As in core vallox.
    _air_temperature_target(
        "supply_air_target_home",
        "settings",
        lambda device: device.settings.home_air_temperature_target,
        lambda device, value: device.async_set_home_air_temperature_target(value),
    ),
    _air_temperature_target(
        "supply_air_target_away",
        "settings",
        lambda device: device.settings.away_air_temperature_target,
        lambda device, value: device.async_set_away_air_temperature_target(value),
    ),
    _air_temperature_target(
        "supply_air_target_boost",
        "settings",
        lambda device: device.settings.boost_air_temperature_target,
        lambda device, value: device.async_set_boost_air_temperature_target(value),
    ),
    # Not in core vallox, which sets these through actions or not at all.
    _air_temperature_target(
        "supply_air_target_extra",
        "configuration",
        lambda device: device.configuration.extra_air_temperature_target,
        lambda device, value: device.async_set_extra_air_temperature_target(value),
        enabled_default=False,
    ),
    _percent(
        "fan_speed_home",
        "settings",
        lambda device: device.settings.home_fan_speed,
        lambda device, value: device.async_set_home_fan_speed(value),
    ),
    _percent(
        "fan_speed_away",
        "settings",
        lambda device: device.settings.away_fan_speed,
        lambda device, value: device.async_set_away_fan_speed(value),
    ),
    _percent(
        "fan_speed_boost",
        "settings",
        lambda device: device.settings.boost_fan_speed,
        lambda device, value: device.async_set_boost_fan_speed(value),
    ),
    _percent(
        "extra_extract_fan",
        "configuration",
        lambda device: device.configuration.extra_extract_fan,
        lambda device, value: device.async_set_extra_extract_fan(value),
        enabled_default=False,
    ),
    _percent(
        "extra_supply_fan",
        "configuration",
        lambda device: device.configuration.extra_supply_fan,
        lambda device, value: device.async_set_extra_supply_fan(value),
        enabled_default=False,
    ),
    _duration(
        "boost_duration",
        "settings",
        lambda device: device.settings.boost_duration,
        lambda device, value: device.async_set_boost_duration(value),
    ),
    _duration(
        "fireplace_duration",
        "settings",
        lambda device: device.settings.fireplace_duration,
        lambda device, value: device.async_set_fireplace_duration(value),
    ),
    _duration(
        "extra_duration",
        "configuration",
        lambda device: device.configuration.extra_duration,
        lambda device, value: device.async_set_extra_duration(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ValloxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Vallox number entities."""
    runtime = entry.runtime_data
    async_add_entities(
        ValloxNumberEntity(runtime.coordinator_for(description.components), description)
        for description in NUMBER_DESCRIPTIONS
    )


class ValloxNumberEntity(ValloxEntity, NumberEntity):
    """A writable Vallox setting."""

    entity_description: ValloxNumberEntityDescription
    _attr_entity_category = EntityCategory.CONFIG

    @property
    @override
    def native_value(self) -> float | None:
        """Return the setting read from the unit."""
        return self.entity_description.value_fn(self.device)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Write the setting to the unit."""
        await self._async_write(self.entity_description.set_fn(self.device, value))
