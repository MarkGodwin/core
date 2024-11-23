"""Support for IP Cameras."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.group.binary_sensor import BinarySensorGroup
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .const import CONF_MOTION_SENSOR


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add Motion and Doorbell sensors related to the camera."""

    to_add = []

    if entry.options.get(CONF_MOTION_SENSOR) not in (None, ""):
        to_add.append(
            BinarySensorMirror(
                entry.entry_id,
                entry.title,
                entry.options.get(CONF_MOTION_SENSOR),
            )
        )

    async_add_entities(to_add)


class BinarySensorMirror(BinarySensorGroup):
    """A binary sensor mirrored from another binary sensor, but linked to the generic camera device."""

    def __init__(
        self,
        identifier,
        title,
        entity_id,
    ) -> None:
        """Initialize a generic camera's linked sensor. We simply use a Group of one to duplicate the sensor."""
        super().__init__(
            identifier + "_motion",
            title + " Motion",
            BinarySensorDeviceClass.MOTION,
            [entity_id],
            None,
        )

        self._dev_unique_id = identifier
        self._title = title

    @property
    def device_info(self) -> DeviceInfo:
        """Return Device description based on camera name."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._dev_unique_id)
            },
            "name": self._title,
            "manufacturer": "Home Assistant",
            "model": "Generic Camera",
        }
