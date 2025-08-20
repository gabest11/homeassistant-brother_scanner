import voluptuous as vol
import logging
import ipaddress
import re
from homeassistant import config_entries
from .const import DOMAIN, MODEL, MANUFACTURER
from .api import find_brother_printer

_LOGGER = logging.getLogger(__name__)


def validate_ip_or_hostname(value: str) -> str:
    value = value.strip()
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        if re.match(r"^(?=.{1,253}$)([a-zA-Z0-9-]{1,63}\.)*[a-zA-Z]{2,63}$", value):
            return value
    raise vol.Invalid("Invalid IP or hostname")


class BrotherScannerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is None:
            detected_ip = await find_brother_printer(self.hass, MODEL)

            if detected_ip:
                _LOGGER.info("Auto-detected Brother printer at %s", detected_ip)
            else:
                _LOGGER.warning("No Brother printer found, leaving IP empty")

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {vol.Required("ip", default=detected_ip or ""): str}
                ),
                description_placeholders={
                    "note": "Printer auto-detection may take a few seconds"
                },
            )

        ip = validate_ip_or_hostname(user_input["ip"])
        await self.async_set_unique_id(ip)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"{MANUFACTURER} {MODEL} Scanner ({ip})",
            data={"ip": ip},
        )
