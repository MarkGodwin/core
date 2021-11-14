"""Platform for scene state switch integration."""
import logging
from typing import List, Optional

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBW,
    COLOR_MODE_RGBWW,
)
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    EVENT_STATE_CHANGED,
    SERVICE_TURN_ON,
)

SCENE_DATA_PLATFORM = "homeassistant_scene"
DATA_PLATFORM = "switch"
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the scene switch platform."""

    # Get the scenes registered with HA
    if SCENE_DATA_PLATFORM not in hass.data:
        return
    scene_platform = hass.data[SCENE_DATA_PLATFORM]

    # Create switch entities to track the scene state
    scene_state_entities = [
        SceneStateSwitch(scene_entity.entity_id, scene_entity.name, scene_entity.icon)
        for scene_entity in scene_platform.entities.values()
    ]

    add_entities(scene_state_entities)

    def _state_changed(evt):
        # If the state change affects our tracked scenes, refresh the scene state tracker
        affected_entities = (
            sse
            for sse in scene_state_entities
            if evt.data[ATTR_ENTITY_ID] in sse.get_tracked_entities()
        )
        for ae in affected_entities:
            ae.schedule_update_ha_state(force_refresh=True)

    # Watch for any state changes
    hass.bus.async_listen(EVENT_STATE_CHANGED, _state_changed)


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up entry."""
    return


class SceneStateSwitch(SwitchEntity):
    """Representation of a Switch."""

    def __init__(self, sceneId, sceneName, icon):
        """Initialize the switch."""
        self._state = False
        self._sceneId = sceneId
        self._sceneName = sceneName
        self._icon = icon
        _LOGGER.info("Creating scene state switch for scene %s", sceneId)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._sceneName + " Scene Switch"

    @property
    def is_on(self):
        """Return true if the entity state matches the scene."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        # Call the service to activate the attached scene
        self._state = True
        await self.hass.services.async_call(
            "scene", SERVICE_TURN_ON, {ATTR_ENTITY_ID: self._sceneId}, blocking=False
        )

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        # You can't turn a scene off, but we will try to re-apply the scene
        self._state = False
        await self.hass.services.async_call(
            "scene", SERVICE_TURN_ON, {ATTR_ENTITY_ID: self._sceneId}, blocking=True
        )
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def icon(self) -> Optional[str]:
        """Return the icon to use in the frontend, if any."""
        return self._icon

    def get_tracked_entities(self) -> List[str]:
        """Get the entities which are tracked by the scene."""
        if self.hass is None:
            return []
        scenePlatform = self.hass.data[SCENE_DATA_PLATFORM]
        if scenePlatform is None:
            return []
        scene = scenePlatform.entities.get(self._sceneId)
        if scene is None:
            return []
        return list(scene.scene_config.states)

    def _compare_simple_state(self, sceneState) -> bool:
        currentState = self.hass.states.get(sceneState.entity_id)
        return currentState is not None and currentState.state == sceneState.state

    def _compare_light_state(self, sceneState) -> bool:
        _LOGGER.debug(
            "%s - Comparing light state for %s(%s)",
            self.name,
            sceneState.name,
            sceneState.entity_id,
        )
        currentState = self.hass.states.get(sceneState.entity_id)
        if currentState is None:
            return False
        if currentState.state != sceneState.state:
            _LOGGER.debug(
                "State does not match: %s != %s", currentState.state, sceneState.state
            )
            return False

        if currentState.state == "off":
            # Off is off, regardless of colour
            _LOGGER.debug("State matches off")
            return True

        # Compare relevant attributes
        supported_color_modes = currentState.attributes.get(
            ATTR_SUPPORTED_COLOR_MODES, []
        )

        fuzzyAttrs = {
            COLOR_MODE_BRIGHTNESS: ATTR_BRIGHTNESS,
            COLOR_MODE_COLOR_TEMP: ATTR_COLOR_TEMP,
        }

        listAttrs = {
            COLOR_MODE_RGB: ATTR_RGB_COLOR,
            COLOR_MODE_RGBW: ATTR_RGBW_COLOR,
            COLOR_MODE_RGBWW: ATTR_RGBWW_COLOR,
        }

        for key in supported_color_modes:
            attr = fuzzyAttrs.get(key)

            if attr is not None:
                _LOGGER.debug(
                    "%s Comparing %s for %s", self.name, attr, sceneState.name
                )
                _LOGGER.debug(
                    "Current %s: %d, Scene state: %d",
                    attr,
                    currentState.attributes.get(attr),
                    sceneState.attributes.get(attr),
                )
                if (
                    abs(
                        currentState.attributes.get(attr)
                        - sceneState.attributes.get(attr)
                    )
                    > 3
                ):
                    return False
            else:
                attr = listAttrs.get(key)
                if attr is not None and currentState.attributes.get(
                    attr
                ) != sceneState.attributes.get(attr):
                    return False

        _LOGGER.debug("All supported colour mode attributes match")
        return True

    def _compare_cover_state(self, sceneState) -> bool:
        _LOGGER.debug(
            "%s - Comparing cover state for %s(%s)",
            self.name,
            sceneState.name,
            sceneState.entity_id,
        )
        currentState = self.hass.states.get(sceneState.entity_id)
        if currentState is None:
            return False
        if currentState.state != sceneState.state:
            _LOGGER.debug(
                "Top-level state does not match: %s != %s",
                currentState.state,
                sceneState.state,
            )
            return False

        if currentState.state == "closed":
            # closed is closed, regardless of position
            _LOGGER.debug("State matches closed")
            return True

        # Compare relevant attributes
        supported_features = currentState.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        fuzzyAttrs = {
            SUPPORT_SET_POSITION: ATTR_CURRENT_POSITION,
            SUPPORT_SET_TILT_POSITION: ATTR_CURRENT_TILT_POSITION,
        }

        for key in fuzzyAttrs.keys():
            if supported_features & key > 0:
                attr = fuzzyAttrs[key]

                _LOGGER.debug(
                    "%s Comparing %s for %s", self.name, attr, sceneState.name
                )
                _LOGGER.debug(
                    "Current %s: %d, Scene state: %d",
                    attr,
                    currentState.attributes.get(attr),
                    sceneState.attributes.get(attr),
                )
                if (
                    abs(
                        currentState.attributes.get(attr)
                        - sceneState.attributes.get(attr)
                    )
                    > 3
                ):
                    return False

        _LOGGER.debug("All supported cover position attributes match")
        return True

    def update(self):
        """Compare the current entity state to the scene state."""
        scenePlatform = self.hass.data[SCENE_DATA_PLATFORM]
        scene = scenePlatform.entities.get(self._sceneId)

        switch = {
            "light": self._compare_light_state,
            "cover": self._compare_cover_state,
        }

        for sceneState in scene.scene_config.states.values():

            comparer = switch.get(sceneState.domain, self._compare_simple_state)
            if comparer is not None:
                if not comparer(sceneState):
                    self._state = False
                    return

        self._state = True
