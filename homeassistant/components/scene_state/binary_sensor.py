"""Platform for scene state binary_sensor integration."""
from typing import Any, List
from homeassistant.const import TEMP_CELSIUS, EVENT_STATE_CHANGED
from homeassistant.helpers.entity import Entity
from homeassistant.components.binary_sensor import BinarySensorEntity
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
DATA_PLATFORM = "binary_sensor"


def setup_platform(hass, config, add_entities, discovery_info=None):

    # Get the scenes registered with HA
    if SCENE_DATA_PLATFORM not in hass.data:
        return
    scene_platform = hass.data[SCENE_DATA_PLATFORM]

    # Create sensor entities to track the scene state
    scene_state_entities = [
        SceneStateSensor(scene_entity.entity_id, scene_entity.name)
        for scene_entity in scene_platform.entities.values()
    ]

    add_entities(scene_state_entities)

    def _state_changed(evt):
        # If the state change affects our tracked scenes, refresh the scene state tracker
        affected_entities = (
            sse
            for sse in scene_state_entities
            if evt.data["entity_id"] in sse.get_tracked_entities()
        )
        for ae in affected_entities:
            ae.schedule_update_ha_state(force_refresh=True)

    # Watch for any state changes
    hass.bus.async_listen(EVENT_STATE_CHANGED, _state_changed)


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up entry."""
    return


class SceneStateSensor(BinarySensorEntity):
    """Representation of a Sensor."""

    def __init__(self, sceneId, sceneName):
        """Initialize the sensor."""
        self._state = False
        self._sceneId = sceneId
        self._sceneName = sceneName

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._sceneName + " State Sensor"

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

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

            if supported_features & SUPPORT_BRIGHTNESS and (
                currentState.attributes.get(ATTR_BRIGHTNESS)
                != sceneState.attributes.get(ATTR_BRIGHTNESS)
            ):
                return False

            if supported_features & SUPPORT_COLOR_TEMP and (
                currentState.attributes.get(ATTR_COLOR_TEMP)
                != sceneState.attributes.get(ATTR_COLOR_TEMP)
            ):
                return False

            if supported_features & SUPPORT_COLOR and (
                currentState.attributes.get(ATTR_RGB_COLOR)
                != sceneState.attributes.get(ATTR_RGB_COLOR)
            ):
                return False

            if supported_features & SUPPORT_WHITE_VALUE and (
                currentState.attributes.get(ATTR_WHITE_VALUE)
                != sceneState.attributes.get(ATTR_WHITE_VALUE)
            ):
                return False
            return True

        return False

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        scenePlatform = self.hass.data[SCENE_DATA_PLATFORM]
        scene = scenePlatform.entities.get(self._sceneId)

        # sceneEntity.sce
        switch = {
            "input_boolean": self._compare_simple_state,
            "input_number": self._compare_simple_state,
            "light": self._compare_light_state,
        }

        for sceneState in scene.scene_config.states.values():

            comparer = switch.get(sceneState.domain, self._compare_simple_state)
            if comparer is not None:
                if not comparer(sceneState):
                    self._state = False
                    return

        self._state = True
