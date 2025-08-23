from homeassistant.components.button import ButtonEntity
from .device import get_device_info
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    ip = entry.data["ip"]
    button = BrotherScannerSnapshotButton(hass, entry)
    async_add_entities([button])


class BrotherScannerSnapshotButton(ButtonEntity):

    _attr_has_entity_name = True

    def __init__(self, hass, entry):
        self._hass = hass
        self._ip = entry.data["ip"]
        self._hostname = entry.data.get("hostname", self._ip)
        self._entry_id = entry.entry_id
        self._attr_icon = "mdi:scanner"
        self._attr_name = "Snapshot"
        self._attr_unique_id = f"{self._entry_id}_snapshot"
        self._attr_device_info = get_device_info(self._entry_id, self._ip)

    async def async_press(self) -> None:
        await self._hass.services.async_call(
            DOMAIN, "snapshot", {"ip": self._ip}, blocking=False
        )
