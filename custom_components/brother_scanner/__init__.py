import voluptuous as vol
import asyncio
import logging
import datetime
import os
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import storage
from .const import DOMAIN, STORAGE_VERSION, STORAGE_KEY_TEMPLATE, SCANS_DIR
from .api import scan_jpeg

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry):
    """Set up Brother scanner from a config entry."""
    ip = entry.data["ip"]
    entry_id = entry.entry_id

    # Store IP and per-device lock
    hass.data.setdefault(DOMAIN, {})[entry_id] = {
        "ip": ip,
        "lock": asyncio.Lock(),
        "entities": [],
        "entry_id": entry_id,
    }

    # Forward entities to HA
    await hass.config_entries.async_forward_entry_setups(entry, ["button", "camera"])

    # Register snapshot service once
    if not hass.services.has_service(DOMAIN, "snapshot"):

        async def snapshot_service_wrapper(call):
            await snapshot_service(hass, call)

        hass.services.async_register(
            DOMAIN,
            "snapshot",
            snapshot_service_wrapper,
            schema=vol.Schema(
                {vol.Required("ip"): str, vol.Optional("filename"): str},
                extra=vol.ALLOW_EXTRA,
            ),
        )

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, "button")
    await hass.config_entries.async_forward_entry_unload(entry, "camera")
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True


async def snapshot_service(hass, call):
    ip = call.data["ip"]
    filename = call.data.get("filename")

    # Find device by IP
    device_data = next((d for d in hass.data[DOMAIN].values() if d["ip"] == ip), None)
    if not device_data:
        raise HomeAssistantError(f"Device {ip} not found")

    lock = device_data["lock"]
    entry_id = device_data["entry_id"]

    if lock.locked():
        _LOGGER.warning("Snapshot already running for %s, skipping call", ip)
        return

    async with lock:
        try:
            jpeg_bytes = await scan_jpeg(ip)

            if not filename:
                now = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                filename = f"{SCANS_DIR}/{ip}_{now}.jpg"

            # If filename is not absolute, save inside HA www
            if not os.path.isabs(filename):
                filename = hass.config.path("www", filename)

            dir_path = os.path.dirname(filename)
            os.makedirs(dir_path, exist_ok=True)

            def write_file():
                with open(filename, "wb") as f:
                    f.write(jpeg_bytes)

            # Save file in executor to avoid blocking event loop
            await hass.async_add_executor_job(write_file)

            _LOGGER.info("Snapshot saved: %s", filename)

            # Save to HA storage for persistence
            store = storage.Store(
                hass, STORAGE_VERSION, STORAGE_KEY_TEMPLATE.format(entry_id=entry_id)
            )
            await store.async_save({"last_snapshot": filename})

            hass.bus.async_fire(
                f"{DOMAIN}_snapshot_saved", {"ip": ip, "filename": filename}
            )

        except OSError as e:
            _LOGGER.error("Failed to save snapshot for %s: %s", ip, e)
            raise HomeAssistantError(f"Failed to save snapshot: {e}")
        except Exception as e:
            _LOGGER.error("Unexpected error during snapshot for %s: %s", ip, e)
            raise HomeAssistantError(f"Unexpected error: {e}")
