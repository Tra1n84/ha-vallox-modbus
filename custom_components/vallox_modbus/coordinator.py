"""Data update coordinators for the Vallox Modbus integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from modbus_connection import ModbusError
from modbus_connection.model import UpdateReport
from vallox_modbus import ValloxDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SETTINGS_COMPONENTS

_LOGGER = logging.getLogger(__name__)

type ValloxConfigEntry = ConfigEntry[ValloxRuntimeData]


class ValloxCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Refresh one group of Vallox components on its own schedule.

    The device object caches the register values. The coordinator data is the
    report of the last poll, which names the components that refreshed.
    """

    config_entry: ValloxConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ValloxConfigEntry,
        device: ValloxDevice,
        poll: Callable[[], Awaitable[UpdateReport]],
        interval: timedelta,
        label: str,
        retry_interval: timedelta | None = None,
    ) -> None:
        """Initialize the coordinator.

        After a poll in which any component failed, the next poll follows after
        ``retry_interval`` instead of ``interval``.
        """
        super().__init__(
            hass,
            _LOGGER,
            name=f"{entry.title} {label}",
            config_entry=entry,
            update_interval=interval,
            # Reports of two polls compare equal while the cached values differ,
            # so listeners must be notified after every poll.
            always_update=True,
        )
        self.device = device
        self._poll = poll
        self._interval = interval
        self._retry_interval = retry_interval or interval
        self._failed: frozenset[str] = frozenset()

    @override
    async def _async_update_data(self) -> UpdateReport:
        """Poll the components and keep partial successes."""
        # Assume failure until the poll proves otherwise. The next refresh is
        # scheduled from this interval after the update, even when it raises.
        self.update_interval = self._retry_interval
        try:
            report = await self._poll()
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        if not report.updated:
            errors = list(report.failed.values())
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={
                    "error": str(errors[0]) if errors else "no component answered"
                },
            )

        for name in sorted(report.failed.keys() - self._failed):
            _LOGGER.warning(
                "%s failed to refresh and is unavailable: %s",
                name,
                report.failed[name],
            )
        for name in sorted(report.updated & self._failed):
            _LOGGER.info("%s is available again", name)
        self._failed = frozenset(report.failed)
        if not report.failed:
            self.update_interval = self._interval
        return report


@dataclass
class ValloxRuntimeData:
    """The device and its two polling coordinators."""

    device: ValloxDevice
    readings: ValloxCoordinator
    settings: ValloxCoordinator

    def coordinator_for(self, components: tuple[str, ...]) -> ValloxCoordinator:
        """Return the coordinator that polls the given components."""
        if all(component in SETTINGS_COMPONENTS for component in components):
            return self.settings
        if any(component in SETTINGS_COMPONENTS for component in components):
            msg = f"components {components} span both coordinators"
            raise ValueError(msg)
        return self.readings
