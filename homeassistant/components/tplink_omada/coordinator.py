"""Generic Omada API coordinator."""

import asyncio
from datetime import timedelta
import logging

from tplink_omada_client import OmadaSiteClient, OmadaSwitchPortDetails
from tplink_omada_client.clients import OmadaWirelessClient
from tplink_omada_client.devices import OmadaGateway, OmadaListDevice, OmadaSwitch
from tplink_omada_client.exceptions import OmadaClientException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

POLL_SWITCH_PORT = 300
POLL_GATEWAY = 300
POLL_CLIENTS = 300
POLL_DEVICES = 900


class OmadaCoordinator[_T](DataUpdateCoordinator[dict[str, _T]]):
    """Coordinator for synchronizing bulk Omada data."""

    def __init__(
        self,
        hass: HomeAssistant,
        omada_client: OmadaSiteClient,
        name: str,
        poll_delay: int | None = 300,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Omada API Data - {name}",
            update_interval=timedelta(seconds=poll_delay) if poll_delay else None,
        )
        self.omada_client = omada_client

    async def _async_update_data(self) -> dict[str, _T]:
        """Fetch data from API endpoint."""
        try:
            async with asyncio.timeout(10):
                return await self.poll_update()
        except OmadaClientException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def poll_update(self) -> dict[str, _T]:
        """Poll the current data from the controller."""
        raise NotImplementedError("Update method not implemented")


class OmadaSwitchPortCoordinator(OmadaCoordinator[OmadaSwitchPortDetails]):
    """Coordinator for getting details about ports on a switch."""

    def __init__(
        self,
        hass: HomeAssistant,
        omada_client: OmadaSiteClient,
        network_switch: OmadaSwitch,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass, omada_client, f"{network_switch.name} Ports", POLL_SWITCH_PORT
        )
        self._network_switch = network_switch

    async def poll_update(self) -> dict[str, OmadaSwitchPortDetails]:
        """Poll a switch's current state."""
        ports = await self.omada_client.get_switch_ports(self._network_switch)
        return {p.port_id: p for p in ports}


class OmadaGatewayCoordinator(OmadaCoordinator[OmadaGateway]):
    """Coordinator for getting details about the site's gateway."""

    def __init__(
        self,
        hass: HomeAssistant,
        omada_client: OmadaSiteClient,
        mac: str,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(hass, omada_client, "Gateway", POLL_GATEWAY)
        self.mac = mac

    async def poll_update(self) -> dict[str, OmadaGateway]:
        """Poll a the gateway's current state."""
        gateway = await self.omada_client.get_gateway(self.mac)
        return {self.mac: gateway}


class OmadaDevicesCoordinator(OmadaCoordinator[OmadaListDevice]):
    """Coordinator for generic device lists from the controller."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        omada_client: OmadaSiteClient,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(hass, omada_client, "DeviceList", POLL_CLIENTS)
        self._config_entry = config_entry

    async def poll_update(self) -> dict[str, OmadaListDevice]:
        """Poll the site's current registered Omada devices."""
        devices = {d.mac: d for d in await self.omada_client.get_devices()}

        self._update_device_registry(devices)

        return devices

    def _update_device_registry(self, devices: dict[str, OmadaListDevice]) -> None:
        device_registry = dr.async_get(self.hass)
        # Remove any devices that are no longer present
        for (
            registered_device
        ) in device_registry.devices.get_devices_for_config_entry_id(
            self._config_entry.entry_id
        ):
            if all(i[1] not in devices for i in registered_device.identifiers):
                entity_registry = er.async_get(self.hass)
                dev_entities = er.async_entries_for_device(
                    entity_registry,
                    registered_device.id,
                    include_disabled_entities=True,
                )
                if not dev_entities:
                    dr.async_remove_device(registered_device.id)

        # Add or update all connected devices
        for device in devices.values():
            dr.async_get_or_create(
                config_entry_id=self._config_entry.entry_id,
                connections={(dr.CONNECTION_NETWORK_MAC, device.mac)},
                identifiers={(DOMAIN, device.mac)},
                manufacturer="TP-Link",
                model=device.model_display_name,
                name=device.name,
            )


class OmadaClientsCoordinator(OmadaCoordinator[OmadaWirelessClient]):
    """Coordinator for getting details about the site's connected clients."""

    def __init__(self, hass: HomeAssistant, omada_client: OmadaSiteClient) -> None:
        """Initialize my coordinator."""
        super().__init__(hass, omada_client, "ClientsList", POLL_CLIENTS)

    async def poll_update(self) -> dict[str, OmadaWirelessClient]:
        """Poll the site's current active wi-fi clients."""
        return {
            c.mac: c
            async for c in self.omada_client.get_connected_clients()
            if isinstance(c, OmadaWirelessClient)
        }
