"""Support for IP Cameras."""

from __future__ import annotations

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.components.group.entity import GroupEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .const import CONF_DOORBELL_SENSOR


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add Motion and Doorbell sensors related to the camera."""

    to_add = []

    if entry.options.get(CONF_DOORBELL_SENSOR) not in (None, ""):
        to_add.append(
            BinarySensorToDoorbellEvent(
                entry.entry_id,
                entry.title,
                entry.options.get(CONF_DOORBELL_SENSOR),
            )
        )

    async_add_entities(to_add)


class BinarySensorToDoorbellEvent(GroupEntity, EventEntity):
    """Representation of an event group."""

    _attr_available = False
    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str | None,
        name: str,
        entity_id: str,
    ) -> None:
        """Initialize an event group."""
        self._title = name
        self._dev_unique_id = unique_id
        self._is_triggered = False
        self._entity_ids = [entity_id]
        self._attr_name = name + " Doorbell"
        self._attr_extra_state_attributes = {ATTR_ENTITY_ID: [entity_id]}
        self._attr_unique_id = unique_id + "_doorbell"
        self._attr_event_class = EventDeviceClass.DOORBELL
        self._attr_event_types = ["single_press"]

    @callback
    def async_update_group_state(self) -> None:
        """Query all members and determine the binary sensor group state."""
        state = self.hass.states.get(self._entity_ids[0])
        self._attr_available = state != STATE_UNAVAILABLE

        if state.state == STATE_ON:
            if not self._is_triggered:
                self._is_triggered = True
                self._trigger_event("single_press", {})
        else:
            self._is_triggered = False

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
