from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, MANUFACTURER, MODEL
from .api import scan_jpeg
import datetime
import logging
import asyncio
import os

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    ip = entry.data["ip"]
    async_add_entities([ScannerButton(hass, ip, entry.entry_id)])


class ScannerButton(ButtonEntity):
    def __init__(self, hass, ip, entry_id):
        self._hass = hass
        self._ip = ip
        self._entry_id = entry_id

        self._attr_name = f"Snapshot ({ip})"
        self._attr_unique_id = f"{entry_id}_snapshot"
        self._attr_icon = "mdi:scanner"

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=f"{MANUFACTURER} {MODEL} Scanner ({self._ip})",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    async def async_press(self) -> None:
        """Schedule snapshot service call without blocking UI."""
        asyncio.create_task(self._call_snapshot_service())

    async def _call_snapshot_service(self):
        """Call the snapshot service safely."""
        try:
            await self._hass.services.async_call(
                DOMAIN, "snapshot", {"ip": self._ip}, blocking=True
            )
        except Exception as e:
            _LOGGER.error("Snapshot service failed for %s: %s", self._ip, e)


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

            dir_path = os.path.dirname(filename)
            if not dir_path:
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
