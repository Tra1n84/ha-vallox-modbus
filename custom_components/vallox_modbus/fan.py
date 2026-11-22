"""Fan platform for the Vallox Modbus integration."""

from collections.abc import Mapping
from typing import Any, override

from vallox_modbus import Profile, SystemMode, ValloxDevice

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, PRESET_MODE_TO_PROFILE, PROFILE_TO_PRESET_MODE
from .coordinator import ValloxConfigEntry, ValloxCoordinator
from .entity import ValloxEntity, ValloxEntityDescription

PARALLEL_UPDATES = 1

FAN_DESCRIPTION = ValloxEntityDescription(
    key="ventilation",
    translation_key="ventilation",
    name=None,
    components=("runtime",),
)


def _profile_fan_speed(device: ValloxDevice, profile: Profile | None) -> int | None:
    """Return the configured fan speed of a profile, if it has one."""
    if profile is Profile.HOME:
        return device.settings.home_fan_speed
    if profile is Profile.AWAY:
        return device.settings.away_fan_speed
    if profile is Profile.BOOST:
        return device.settings.boost_fan_speed
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ValloxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Vallox fan."""
    runtime = entry.runtime_data
    async_add_entities([ValloxFanEntity(runtime.readings, runtime.settings)])


class ValloxFanEntity(ValloxEntity, FanEntity):
    """The ventilation of a Vallox unit.

    As in the core vallox integration, the percentage is the configured fan
    speed of the active profile, not the live fan speed.
    """

    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _attr_preset_modes = list(PRESET_MODE_TO_PROFILE)

    def __init__(
        self, readings: ValloxCoordinator, settings: ValloxCoordinator
    ) -> None:
        """Initialize the fan."""
        super().__init__(readings, FAN_DESCRIPTION)
        self._settings = settings
        # The core vallox fan uses the bare device id as its unique ID.
        self._attr_unique_id = readings.config_entry.entry_id

    @override
    async def async_added_to_hass(self) -> None:
        """Also update when the profile speed settings refresh."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._settings.async_add_listener(self._handle_coordinator_update)
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the unit is in normal operation."""
        if (mode := self.device.runtime.system_mode) is None:
            return None
        return mode is SystemMode.NORMAL

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return the active profile, if it is a selectable preset."""
        preset = PROFILE_TO_PRESET_MODE.get(self.device.profile)
        return preset if preset in PRESET_MODE_TO_PROFILE else None

    @property
    @override
    def percentage(self) -> int | None:
        """Return the configured fan speed of the active profile."""
        if not self._settings_available:
            return None
        return _profile_fan_speed(self.device, self.device.profile)

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, int | None]:
        """Return the configured fan speeds, as in the core vallox fan."""
        available = self._settings_available
        return {
            f"fan_speed_{preset}": _profile_fan_speed(self.device, profile)
            if available
            else None
            for preset, profile in (
                ("home", Profile.HOME),
                ("away", Profile.AWAY),
                ("boost", Profile.BOOST),
            )
        }

    @property
    def _settings_available(self) -> bool:
        """Return whether the profile speed settings refreshed."""
        return (
            self._settings.last_update_success
            and "settings" in self._settings.data.updated
        )

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Activate a profile."""
        await self._async_write(
            self.device.async_set_profile(PRESET_MODE_TO_PROFILE[preset_mode]),
            self.coordinator,
        )

    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the unit on, optionally with a speed and a preset."""
        if percentage == 0:
            await self.async_turn_off()
            return

        # As in the core vallox fan: set the speed of the target profile first,
        # so a preset without a speed setting fails before anything is written.
        # Power on last, so the unit starts in its final profile and speed.
        if percentage is not None:
            await self._async_set_profile_fan_speed(percentage, preset_mode)
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        await self._async_write(self.device.async_set_power(True), self.coordinator)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch the unit off."""
        await self._async_write(self.device.async_set_power(False), self.coordinator)

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the configured fan speed of the active profile."""
        if percentage == 0:
            await self.async_turn_off()
            return
        await self._async_set_profile_fan_speed(percentage)

    async def _async_set_profile_fan_speed(
        self, percentage: int, preset_mode: str | None = None
    ) -> None:
        """Set the fan speed of the given preset, or of the active profile."""
        profile = (
            PRESET_MODE_TO_PROFILE[preset_mode]
            if preset_mode is not None
            else self.device.profile
        )
        if profile is Profile.HOME:
            write = self.device.async_set_home_fan_speed(percentage)
        elif profile is Profile.AWAY:
            write = self.device.async_set_away_fan_speed(percentage)
        elif profile is Profile.BOOST:
            write = self.device.async_set_boost_fan_speed(percentage)
        else:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="preset_without_fan_speed",
                translation_placeholders={
                    "preset_mode": PROFILE_TO_PRESET_MODE.get(profile, str(profile))
                },
            )
        await self._async_write(write, self._settings)
