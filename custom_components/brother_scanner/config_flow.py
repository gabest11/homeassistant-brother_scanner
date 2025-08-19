import voluptuous as vol
import ipaddress
import re
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN, MANUFACTURER, MODEL


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
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({vol.Required("ip"): str}),
            )

        ip = validate_ip_or_hostname(user_input["ip"])

        await self.async_set_unique_id(ip)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"{MANUFACTURER} {MODEL} ({ip})",
            data={"ip": ip},
        )
