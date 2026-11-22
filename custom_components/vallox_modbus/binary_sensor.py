"""Binary sensor platform for the Vallox Modbus integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from vallox_modbus import ValloxDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ValloxConfigEntry
from .entity import ValloxEntity, ValloxEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ValloxBinarySensorEntityDescription(
    BinarySensorEntityDescription, ValloxEntityDescription
):
    """Describes a Vallox binary sensor."""

    value_fn: Callable[[ValloxDevice], bool | None]


# The core vallox post_heater sensor reads A_CYC_IO_HEATER (4868), which the
# Vallox Modbus manual does not document, so it is not available here.
BINARY_SENSOR_DESCRIPTIONS: tuple[ValloxBinarySensorEntityDescription, ...] = (
    ValloxBinarySensorEntityDescription(
        key="defrosting",
        translation_key="defrosting",
        components=("runtime",),
        value_fn=lambda device: device.runtime.defrosting,
    ),
    ValloxBinarySensorEntityDescription(
        key="fault",
        translation_key="fault",
        components=("runtime",),
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda device: device.runtime.fault,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ValloxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Vallox binary sensors."""
    runtime = entry.runtime_data
    async_add_entities(
        ValloxBinarySensorEntity(
            runtime.coordinator_for(description.components), description
        )
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class ValloxBinarySensorEntity(ValloxEntity, BinarySensorEntity):
    """A Vallox binary sensor."""

    entity_description: ValloxBinarySensorEntityDescription
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the sensor state."""
        return self.entity_description.value_fn(self.device)
