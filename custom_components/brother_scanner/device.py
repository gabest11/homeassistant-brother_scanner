from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, MANUFACTURER, MODEL
import re


def get_device_info(entry_id: str, ip: str) -> DeviceInfo:
    """Return shared DeviceInfo for a Brother scanner."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name=f"{MODEL} {ip}",
        manufacturer=MANUFACTURER,
        model=MODEL,
        configuration_url=f"http://{ip}",
    )
