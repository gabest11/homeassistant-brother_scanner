from homeassistant.components.button import ButtonEntity
from .device import get_device_info
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    ip = entry.data["ip"]
    button = BrotherScannerSnapshotButton(hass, ip, entry.entry_id)
    async_add_entities([button])


class BrotherScannerSnapshotButton(ButtonEntity):

    _attr_has_entity_name = True

    def __init__(self, hass, ip, entry_id):
        self._hass = hass
        self._ip = ip
        self._entry_id = entry_id
        self._attr_icon = "mdi:scanner"
        self._attr_name = "Snapshot"
        self._attr_unique_id = f"{entry_id}_snapshot"
        self._attr_device_info = get_device_info(entry_id, ip)

    async def async_press(self) -> None:
        await self._hass.services.async_call(
            DOMAIN, "snapshot", {"ip": self._ip}, blocking=False
        )
