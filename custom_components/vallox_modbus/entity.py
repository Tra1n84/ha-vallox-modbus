"""Base entity for the Vallox Modbus integration."""

from collections.abc import Awaitable
from dataclasses import dataclass
from typing import override

from vallox_modbus import (
    ValloxDevice,
    ValloxError,
    ValloxInvalidInputError,
    ValloxPartialWriteError,
)

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import ValloxCoordinator


@dataclass(frozen=True, kw_only=True)
class ValloxEntityDescription(EntityDescription):
    """Describes a Vallox entity and the device components it reads."""

    components: tuple[str, ...]


class ValloxEntity(CoordinatorEntity[ValloxCoordinator]):
    """Common identity, device info and write handling for Vallox entities.

    Unique IDs follow the core vallox scheme ``<device id>-<key>``. Modbus has
    no documented device identity, so the config entry ID is the device id.
    """

    entity_description: ValloxEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ValloxCoordinator,
        entity_description: ValloxEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}-{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=MANUFACTURER,
            name=entry.title,
        )

    @property
    def device(self) -> ValloxDevice:
        """Return the Vallox device."""
        return self.coordinator.device

    @property
    @override
    def available(self) -> bool:
        """Return whether every component this entity reads refreshed."""
        return super().available and all(
            component in self.coordinator.data.updated
            for component in self.entity_description.components
        )

    async def _async_write(
        self, write: Awaitable[None], *refresh: ValloxCoordinator
    ) -> None:
        """Run a device write, translate its errors and refresh afterwards.

        Writes do not update the cached values, so the coordinators that poll
        the written components refresh even after a failed write.
        """
        try:
            await write
        except ValloxInvalidInputError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_input",
                translation_placeholders={"error": str(err)},
            ) from err
        except ValloxPartialWriteError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="partial_write",
                translation_placeholders={"error": str(err)},
            ) from err
        except ValloxError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        finally:
            for coordinator in refresh or (self.coordinator,):
                await coordinator.async_request_refresh()
