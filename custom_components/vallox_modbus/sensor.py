"""Sensor platform for the Vallox Modbus integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time
from typing import override

from vallox_modbus import SystemMode, ValloxDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfRatio,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import CELL_STATE_TO_STR, PROFILE_TO_PRESET_MODE
from .coordinator import ValloxConfigEntry
from .entity import ValloxEntity, ValloxEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ValloxSensorEntityDescription(SensorEntityDescription, ValloxEntityDescription):
    """Describes a Vallox sensor."""

    value_fn: Callable[[ValloxDevice], StateType | datetime]


def _fan_speed(device: ValloxDevice, value: int | None) -> int | None:
    """Return a fan speed, or 0 while the unit is off, as in core vallox."""
    if (mode := device.runtime.system_mode) is None:
        return None
    # The unit keeps reporting its last fan speeds after it is turned off.
    return value if mode is SystemMode.NORMAL else 0


def _next_filter_change(device: ValloxDevice) -> datetime | None:
    """Return when the filter is due for a change, as in core vallox."""
    if (next_change := device.next_filter_change_date) is None:
        return None
    return datetime.combine(
        next_change, time(hour=13, tzinfo=dt_util.get_default_time_zone())
    )


def _temperature(
    key: str, value_fn: Callable[[ValloxDevice], float | None], component: str
) -> ValloxSensorEntityDescription:
    """Describe a temperature sensor."""
    return ValloxSensorEntityDescription(
        key=key,
        translation_key=key,
        components=(component,),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=value_fn,
    )


SENSOR_DESCRIPTIONS: tuple[ValloxSensorEntityDescription, ...] = (
    _temperature(
        "extract_air",
        lambda device: device.measurements.extract_air_temperature,
        "measurements",
    ),
    _temperature(
        "exhaust_air",
        lambda device: device.measurements.exhaust_air_temperature,
        "measurements",
    ),
    _temperature(
        "outdoor_air",
        lambda device: device.measurements.outdoor_air_temperature,
        "measurements",
    ),
    _temperature(
        "supply_air",
        lambda device: device.measurements.supply_air_temperature,
        "measurements",
    ),
    _temperature(
        "supply_cell_air",
        lambda device: device.measurements.supply_cell_air_temperature,
        "measurements",
    ),
    ValloxSensorEntityDescription(
        key="optional_air",
        translation_key="optional_air",
        components=("sensors",),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.sensors.optional_temperature,
    ),
    ValloxSensorEntityDescription(
        key="humidity",
        components=("measurements",),
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.measurements.humidity,
    ),
    ValloxSensorEntityDescription(
        key="co2",
        components=("measurements",),
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.measurements.co2,
    ),
    ValloxSensorEntityDescription(
        key="current_profile",
        translation_key="current_profile",
        components=("runtime",),
        device_class=SensorDeviceClass.ENUM,
        options=list(PROFILE_TO_PRESET_MODE.values()),
        value_fn=lambda device: PROFILE_TO_PRESET_MODE.get(device.profile),
    ),
    ValloxSensorEntityDescription(
        key="fan_speed",
        translation_key="fan_speed",
        components=("measurements", "runtime"),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: _fan_speed(device, device.measurements.fan_speed),
    ),
    ValloxSensorEntityDescription(
        key="extract_fan_speed",
        translation_key="extract_fan_speed",
        components=("measurements", "runtime"),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        entity_registry_enabled_default=False,
        value_fn=lambda device: _fan_speed(device, device.measurements.extract_fan_rpm),
    ),
    ValloxSensorEntityDescription(
        key="supply_fan_speed",
        translation_key="supply_fan_speed",
        components=("measurements", "runtime"),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        entity_registry_enabled_default=False,
        value_fn=lambda device: _fan_speed(device, device.measurements.supply_fan_rpm),
    ),
    ValloxSensorEntityDescription(
        key="remaining_time_for_filter",
        translation_key="remaining_time_for_filter",
        components=("settings", "configuration"),
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_next_filter_change,
    ),
    ValloxSensorEntityDescription(
        key="cell_state",
        translation_key="cell_state",
        components=("runtime",),
        device_class=SensorDeviceClass.ENUM,
        options=list(CELL_STATE_TO_STR.values()),
        value_fn=lambda device: CELL_STATE_TO_STR.get(
            device.runtime.heat_exchanger_state
        ),
    ),
    ValloxSensorEntityDescription(
        key="profile_duration",
        translation_key="profile_duration",
        components=("runtime", "timer_switches"),
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda device: device.remaining_profile_duration,
    ),
    # Not in core vallox: the remaining days the unit itself counts down.
    ValloxSensorEntityDescription(
        key="filter_remaining",
        translation_key="filter_remaining",
        components=("runtime",),
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda device: device.runtime.filter_remaining,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ValloxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Vallox sensors."""
    runtime = entry.runtime_data
    async_add_entities(
        ValloxSensorEntity(runtime.coordinator_for(description.components), description)
        for description in SENSOR_DESCRIPTIONS
    )


class ValloxSensorEntity(ValloxEntity, SensorEntity):
    """A Vallox sensor."""

    entity_description: ValloxSensorEntityDescription
    # As in core vallox, every sensor is a diagnostic entity.
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.device)
