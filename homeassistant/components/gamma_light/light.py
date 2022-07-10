"""Light support for switch entities."""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_XY_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import GAMMA, MIN_BRIGHTNESS


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Light Switch config entry."""
    registry = er.async_get(hass)
    entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_ENTITY_ID]
    )
    wrapped_switch = registry.async_get(entity_id)

    device_id = wrapped_switch.device_id if wrapped_switch else None

    min_brightness = int(config_entry.options[MIN_BRIGHTNESS])
    gamma = float(config_entry.options[GAMMA])

    async_add_entities(
        [
            GammaAdjustedLight(
                config_entry.title,
                entity_id,
                config_entry.entry_id,
                device_id,
                min_brightness,
                gamma,
            )
        ]
    )


class GammaAdjustedLight(LightEntity):
    """Represents a Switch as a Light."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    _attr_should_poll = False

    def __init__(
        self,
        name: str,
        light_entity_id: str,
        unique_id: str | None,
        device_id: str | None = None,
        min_brightness: int = 0,
        gamma: float = 1.0,
    ) -> None:
        """Initialize Light wrapper."""
        self._device_id = device_id
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._light_entity_id = light_entity_id
        self._min_brightness = min_brightness
        self._gamma = gamma

    @callback
    def async_state_changed_listener(self, event: Event | None = None) -> None:
        """Handle child updates."""
        if (
            state := self.hass.states.get(self._light_entity_id)
        ) is None or state.state == STATE_UNAVAILABLE:
            self._attr_available = False
            return

        # Set light modes according to child entity
        supported_modes = state.attributes.get(ATTR_SUPPORTED_COLOR_MODES, [])
        if (
            ColorMode.HS in supported_modes
            or ColorMode.RGB in supported_modes
            or ColorMode.XY in supported_modes
            or ColorMode.RGBW in supported_modes
            or ColorMode.RGBWW in supported_modes
        ) and self._attr_color_mode != ColorMode.XY:
            self._attr_color_mode = ColorMode.XY
            self._attr_supported_color_modes = {self._attr_color_mode}
        elif (
            ColorMode.COLOR_TEMP in supported_modes
            and self._attr_color_mode != ColorMode.COLOR_TEMP
        ):
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_supported_color_modes = {self._attr_color_mode}
        elif (
            ColorMode.COLOR_TEMP in supported_modes
            and self._attr_color_mode != ColorMode.BRIGHTNESS
        ):
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {self._attr_color_mode}

        self._attr_is_on = state.state == STATE_ON

        if self._attr_is_on:

            # Calculate the adjusted brightness from the actual dimmer value
            brightness = state.attributes[ATTR_BRIGHTNESS]
            brightness_pct = brightness * 100 / 255
            brightness_adjusted = max(0, (brightness_pct - self._min_brightness)) / (
                100 - self._min_brightness
            )
            brightness_gamma = pow(brightness_adjusted, 1 / self._gamma)
            self._attr_brightness = round(brightness_gamma * 255)

            # Copy across the hue and color temp, if applicable.
            if self._attr_color_mode == ColorMode.XY:
                self._attr_xy_color = state.attributes[ATTR_XY_COLOR]

            if self._attr_color_mode == ColorMode.COLOR_TEMP:
                self._attr_color_temp = state.attributes[ATTR_COLOR_TEMP]

        self._attr_available = True

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def _async_state_changed_listener(event: Event | None = None) -> None:
            """Handle child updates."""
            self.async_state_changed_listener(event)
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._light_entity_id], _async_state_changed_listener
            )
        )

        # Call once on adding
        _async_state_changed_listener()

        # Add this entity to the wrapped switch's device
        registry = er.async_get(self.hass)
        if registry.async_get(self.entity_id) is not None:
            registry.async_update_entity(self.entity_id, device_id=self._device_id)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward the turn_on command to the underlying light."""

        svc_args = {ATTR_ENTITY_ID: self._light_entity_id}

        # Calculate the target brightness
        if ATTR_BRIGHTNESS in kwargs:
            target_brightness = kwargs[ATTR_BRIGHTNESS]
            if target_brightness > 0:
                # Adjust for gammma
                target_brightness_gamma = (
                    pow(target_brightness / 255, self._gamma) * 100
                )
                # Adjust for minimum
                target_brightness_pct = (
                    target_brightness_gamma * (100 - self._min_brightness) / 100
                    + self._min_brightness
                )
                target_brightness = max(1, round(target_brightness_pct * 255 / 100))
            svc_args[ATTR_BRIGHTNESS] = target_brightness

        # Pass through any colour attributes
        if ATTR_XY_COLOR in kwargs:
            svc_args[ATTR_XY_COLOR] = kwargs[ATTR_XY_COLOR]

        if ATTR_COLOR_TEMP in kwargs:
            svc_args[ATTR_COLOR_TEMP] = kwargs[ATTR_COLOR_TEMP]

        await self.hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            svc_args,
            blocking=True,
            context=self._context,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward the turn_off command to the underlying light."""
        await self.hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: self._light_entity_id},
            blocking=True,
            context=self._context,
        )
