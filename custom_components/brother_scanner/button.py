from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, MANUFACTURER, MODEL, DEVICE
from .api import scan_jpeg
import datetime
import logging
import asyncio
import os

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up scanner button entity for a config entry."""
    ip = entry.data["ip"]
    button = BrotherScannerButton(hass, ip, entry.entry_id)

    # Register entity in hass.data so it can be updated on IP change
    hass.data[DOMAIN][entry.entry_id]["entities"].append(button)
    async_add_entities([button])


class BrotherScannerButton(ButtonEntity):
    def __init__(self, hass, ip, entry_id):
        self._hass = hass
        self._ip = ip
        self._entry_id = entry_id
        self._attr_icon = "mdi:scanner"
        self._attr_name = f"Snapshot ({ip})"
        self._attr_unique_id = f"{entry_id}_snapshot"
        self._attr_device_info = self.device_info

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=f"{DEVICE} ({self._ip})",
            manufacturer=MANUFACTURER,
            model=MODEL,
            configuration_url=f"http://{self._ip}",
        )

    @property
    def ip(self):
        """Get current IP from entry data (dynamic)."""
        return self._hass.data[DOMAIN][self._entry_id]["ip"]

    async def async_press(self) -> None:
        """Call snapshot service using current IP."""
        asyncio.create_task(self._call_snapshot_service())

    async def _call_snapshot_service(self):
        try:
            await self._hass.services.async_call(
                DOMAIN, "snapshot", {"ip": self.ip}, blocking=True
            )
        except Exception as e:
            _LOGGER.error("Snapshot service failed for %s: %s", self.ip, e)


async def fetch_and_return_jpeg(hass, ip: str, filename: str, lock: asyncio.Lock):
    """Fetch snapshot and save to file safely with per-device lock."""
    if lock.locked():
        _LOGGER.warning("Snapshot already running for %s, skipping call", ip)
        return

    async with lock:
        try:
            jpeg_bytes = await scan_jpeg(ip)

            if not filename:
                now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"snapshot_{ip}_{now}.jpg"

            # If filename is not absolute, save inside HA www/snapshots
            if not os.path.isabs(filename):
                filename = hass.config.path("www", "snapshots", filename)

            dir_path = os.path.dirname(filename)
            os.makedirs(dir_path, exist_ok=True)

            # Save file in executor to avoid blocking event loop
            await hass.async_add_executor_job(
                lambda: open(filename, "wb").write(jpeg_bytes)
            )

            _LOGGER.info("Snapshot saved: %s", filename)

            hass.bus.async_fire(
                f"{DOMAIN}_snapshot_saved", {"ip": ip, "filename": filename}
            )

        except Exception as e:
            _LOGGER.error("Failed to save snapshot for %s: %s", ip, e)
