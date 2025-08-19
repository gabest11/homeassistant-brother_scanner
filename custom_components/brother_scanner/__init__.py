import asyncio
import logging
import voluptuous as vol
from homeassistant.helpers import entity_platform
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN
from .button import fetch_and_return_jpeg

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry):
    ip = entry.data["ip"]
    entry_id = entry.entry_id

    # Store IP and per-device lock
    hass.data.setdefault(DOMAIN, {})[entry_id] = {"ip": ip, "lock": asyncio.Lock()}

    # Setup button platform
    await hass.config_entries.async_forward_entry_setups(entry, ["button"])

    # Register the service once
    if not hass.services.has_service(DOMAIN, "snapshot"):

        async def snapshot_service(call):
            ip = call.data["ip"]
            filename = call.data.get("filename")

            # Find device by IP
            device_data = None
            for data in hass.data[DOMAIN].values():
                if data["ip"] == call.data["ip"]:
                    device_data = data
                    break
            if not device_data:
                raise HomeAssistantError(f"Device {call.data['ip']} not found")
            lock = device_data["lock"]

            await fetch_and_return_jpeg(hass, ip, filename, lock)

        hass.services.async_register(
            DOMAIN,
            "snapshot",
            snapshot_service,
            schema=vol.Schema(
                {
                    vol.Required("ip"): str,
                    vol.Optional("filename"): str,
                },
                extra=vol.ALLOW_EXTRA,
            ),
        )

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, "button")

    # Remove device data; service remains if other devices exist
    hass.data[DOMAIN].pop(entry.entry_id, None)

    return True
