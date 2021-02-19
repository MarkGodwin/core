"""Platform for scene state switch integration."""
from typing import Any, List, Optional
from homeassistant.const import (
    TEMP_CELSIUS,
    EVENT_STATE_CHANGED,
    SERVICE_TURN_ON,
    ATTR_ENTITY_ID,
)
from homeassistant.helpers.entity import Entity
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.light import (
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR_TEMP,
    SUPPORT_EFFECT,
    SUPPORT_COLOR,
    SUPPORT_TRANSITION,
    SUPPORT_WHITE_VALUE,
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_RGB_COLOR,
    ATTR_WHITE_VALUE,
)

SCENE_DATA_PLATFORM = "homeassistant_scene"
DATA_PLATFORM = "switch"


def setup_platform(hass, config, add_entities, discovery_info=None):

    # Get the scenes registered with HA
    if SCENE_DATA_PLATFORM not in hass.data:
        return
    scene_platform = hass.data[SCENE_DATA_PLATFORM]

    # Create switch entities to track the scene state
    scene_state_entities = [
        SceneStateSwitch(scene_entity.entity_id, scene_entity.name)
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

    def __init__(self, sceneId, sceneName):
        """Initialize the switch."""
        self._state = False
        self._sceneId = sceneId
        self._sceneName = sceneName

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
            "scene", SERVICE_TURN_ON, {ATTR_ENTITY_ID: self._sceneId}, blocking=True
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
        return "mdi:palette-outline"

    def get_tracked_entities(self) -> List[str]:
        if self.hass is None:
            return []
        scenePlatform = self.hass.data[SCENE_DATA_PLATFORM]
        if scenePlatform is None:
            return []
        scene = scenePlatform.entities.get(self._sceneId)
        if scene is None:
            return []
        return [entity_id for entity_id in scene.scene_config.states]

    def _compare_simple_state(self, sceneState) -> bool:
        return self.hass.states.get(sceneState.entity_id).state == sceneState.state

    def _compare_light_state(self, sceneState) -> bool:
        currentState = self.hass.states.get(sceneState.entity_id)
        if currentState.state == sceneState.state:
            # Compare relevant attributes
            supported_features = currentState.attributes.get("supported_features", 0)

            attrs_to_check = {
                SUPPORT_BRIGHTNESS: ATTR_BRIGHTNESS,
                SUPPORT_COLOR_TEMP: ATTR_COLOR_TEMP,
                SUPPORT_COLOR: ATTR_RGB_COLOR,
                SUPPORT_WHITE_VALUE: ATTR_WHITE_VALUE,
            }

            for key in attrs_to_check.keys():
                attr = attrs_to_check[key]
                if supported_features & key and currentState.attributes.get(
                    attr
                ) != sceneState.attributes.get(attr):
                    return False

            return True

        return False

    def update(self):
        """
        Compare the current entity state to the scene state
        """
        scenePlatform = self.hass.data[SCENE_DATA_PLATFORM]
        scene = scenePlatform.entities.get(self._sceneId)

        switch = {
            "light": self._compare_light_state,
        }

        for sceneState in scene.scene_config.states.values():

            comparer = switch.get(sceneState.domain, self._compare_simple_state)
            if comparer is not None:
                if not comparer(sceneState):
                    self._state = False
                    return

        self._state = True
