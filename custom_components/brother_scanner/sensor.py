from homeassistant.components.sensor import SensorEntity
from .device import get_device_info
from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    ip = entry.data["ip"]
    sensor = BrotherScannerLastSnapshotSensor(hass, ip, entry.entry_id)
    async_add_entities([sensor], update_before_add=True)


class BrotherScannerLastSnapshotSensor(SensorEntity):
    """Text sensor to store last snapshot filename."""

    _attr_has_entity_name = True

    def __init__(self, hass, ip, entry_id):
        self._hass = hass
        self._ip = ip
        self._entry_id = entry_id
        self._attr_name = "Last Snapshot"
        self._attr_unique_id = f"{entry_id}_last_snapshot"
        self._attr_native_value = None
        self._attr_device_info = get_device_info(entry_id, ip)
        # Listen to snapshot saved events for this IP
        hass.bus.async_listen(f"{DOMAIN}_snapshot_saved", self._handle_snapshot_saved)

    @property
    def state(self):
        return self._attr_native_value

    async def _handle_snapshot_saved(self, event):
        """Update sensor when snapshot service saves a file."""
        data = event.data
        if data.get("ip") == self._ip:
            filename = data.get("filename")
            _LOGGER.debug("Updating snapshot sensor for %s: %s", self._ip, filename)
            self._attr_native_value = filename
            self.async_write_ha_state()
