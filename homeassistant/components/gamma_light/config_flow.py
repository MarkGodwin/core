"""Config flow for gamma_light."""

from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.helpers import config_entry_flow
from homeassistant.helpers import entity_registry

from .const import DOMAIN


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""
    # TODO Check if there are any devices that can be discovered in the network.

    registry = entity_registry.async_get(hass)

    potential_lights = [
        entry
        for entry in registry.entities.values()
        if entry.domain == Platform.LIGHT and entry.platform != DOMAIN
    ]

    # Exclude any lights we have already wrapped

    return len(potential_lights) > 0
    # devices = await hass.async_add_executor_job(my_pypi_dependency.discover)
    # return len(devices) > 0


config_entry_flow.register_discovery_flow(DOMAIN, "gamma_light", _async_has_devices)
