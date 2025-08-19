import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, MANUFACTURER, MODEL


class ScannerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Scanner integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step when adding a Scanner device."""
        if user_input is None:
            # Show form to enter device IP
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("ip"): str,
                    }
                ),
            )

        # Create the config entry with the IP and a descriptive title
        return self.async_create_entry(
            title=f"{MANUFACTURER} {MODEL} ({user_input['ip']})", data=user_input
        )
