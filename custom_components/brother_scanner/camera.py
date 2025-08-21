import logging
import os
import time
import functools
from homeassistant.components.camera import Camera
from homeassistant.helpers import storage
from .device import get_device_info
from .const import DOMAIN, STORAGE_VERSION, STORAGE_KEY_TEMPLATE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Brother scanner camera entity."""
    ip = entry.data["ip"]
    camera = BrotherScannerLastSnapshot(hass, ip, entry.entry_id)
    async_add_entities([camera], update_before_add=True)


class BrotherScannerLastSnapshot(Camera):
    """Camera entity showing the last snapshot from the Brother scanner."""

    _attr_has_entity_name = True

    def __init__(self, hass, ip, entry_id):
        super().__init__()
        self._hass = hass
        self._ip = ip
        self._entry_id = entry_id
        self._attr_name = "Last Snapshot"
        self._attr_unique_id = f"{entry_id}_last_snapshot"
        self._attr_device_info = get_device_info(entry_id, ip)

        # Path to last snapshot file
        self._file_path: str | None = None
        # Timestamp of last snapshot, used for cache-busting
        self._last_update_ts: float | None = None

        # Listen for snapshot events → refresh camera immediately
        hass.bus.async_listen(f"{DOMAIN}_snapshot_saved", self._handle_snapshot_saved)

    async def async_added_to_hass(self):
        """Restore last snapshot path from storage."""
        store = storage.Store(
            self._hass,
            STORAGE_VERSION,
            STORAGE_KEY_TEMPLATE.format(entry_id=self._entry_id),
        )

        data = await store.async_load()
        if data and (last_snapshot := data.get("last_snapshot")):
            self._file_path = last_snapshot
            if os.path.exists(last_snapshot):
                self._last_update_ts = os.path.getctime(last_snapshot)
            _LOGGER.debug(
                "Restored last snapshot for %s: %s", self._ip, self._file_path
            )
            self.async_write_ha_state()

    async def async_camera_image(self, width=None, height=None):
        """Return the latest snapshot image bytes (non-blocking)."""
        if not self._file_path or not os.path.exists(self._file_path):
            return None

        def read_file(path):
            with open(path, "rb") as f:
                return f.read()

        try:
            return await self._hass.async_add_executor_job(
                functools.partial(read_file, self._file_path)
            )
        except Exception as e:
            _LOGGER.error("Failed to read snapshot image: %s", e)
            return None

    @property
    def available(self):
        """Camera is available if the last snapshot exists."""
        return bool(self._file_path and os.path.exists(self._file_path))

    @property
    def entity_picture(self):
        """Return the entity picture URL for sidebar/picture-entity, with cache-busting."""
        if self._file_path and os.path.exists(self._file_path):
            ts = int(self._last_update_ts) if self._last_update_ts else int(time.time())
            local_path = self._file_path.replace(
                f"{self._hass.config.path('www')}", "/local"
            )
            return f"{local_path}?t={ts}"
        return None

    @property
    def extra_state_attributes(self):
        """Expose timestamp so frontend refreshes still images."""
        return {
            "last_update": int(self._last_update_ts) if self._last_update_ts else None
        }

    async def _handle_snapshot_saved(self, event):
        """Update camera when a new snapshot is saved."""
        data = event.data
        if data.get("ip") != self._ip or not (filename := data.get("filename")):
            return

        self._file_path = filename
        self._last_update_ts = time.time()
        _LOGGER.debug("Refreshing camera entity for %s: %s", self._ip, self._file_path)
        self.async_write_ha_state()
