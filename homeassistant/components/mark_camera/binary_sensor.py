"""Support for IP Cameras."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OCCUPANCY,
)
from homeassistant.components.group.binary_sensor import BinarySensorGroup
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .const import CONF_DOORBELL_SENSOR, CONF_MOTION_SENSOR


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add Motion and Doorbell sensors related to the camera."""

    to_add = []

    if entry.options.get(CONF_MOTION_SENSOR) not in (None, ""):
        to_add.append(
            BinarySensorMirror(
                hass,
                entry.unique_id,
                True,
                entry.title,
                entry.options.get(CONF_MOTION_SENSOR),
            )
        )

    if entry.options.get(CONF_DOORBELL_SENSOR) not in (None, ""):
        to_add.append(
            BinarySensorMirror(
                hass,
                entry.unique_id,
                False,
                entry.title,
                entry.options.get(CONF_DOORBELL_SENSOR),
            )
        )

    async_add_entities(to_add)


class BinarySensorMirror(BinarySensorGroup):
    """A binary sensor mirrored from another binary sensor, but linked to the generic camera device."""

    def __init__(
        self,
        hass: HomeAssistant,
        identifier,
        usage: bool,
        title,
        entity_id,
    ):
        """Initialize a generic camera's linked sensor. We simply use a Group of one to duplicate the sensor."""
        super().__init__(
            identifier + ("_motion" if usage else "_doorbell"),
            title + (" Motion" if usage else " Doorbell"),
            DEVICE_CLASS_MOTION if usage else DEVICE_CLASS_OCCUPANCY,
            [entity_id],
            None,
        )
        self.hass = hass

        self._dev_unique_id = identifier
        self._title = title

    @property
    def device_info(self):
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
