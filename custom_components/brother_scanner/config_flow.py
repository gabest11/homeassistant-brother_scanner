import voluptuous as vol
import asyncio
import ipaddress
import re
import socket
import logging
from homeassistant import config_entries
from homeassistant.components import zeroconf as ha_zeroconf
from zeroconf import ServiceBrowser
from .const import DOMAIN, MODEL, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


def normalize_address(value: bytes | str) -> str:
    """Normalize an IP or hostname (from user input or zeroconf)."""
    if isinstance(value, bytes):
        # Convert raw bytes to IP
        if len(value) == 4:
            return socket.inet_ntoa(value)  # IPv4
        elif len(value) == 16:
            return socket.inet_ntop(socket.AF_INET6, value)  # IPv6
        raise vol.Invalid("Invalid raw address length")

    if isinstance(value, str):
        value = value.strip()
        # Try IP first
        try:
            ipaddress.ip_address(value)
            return value
        except ValueError:
            # Fallback: validate hostname
            if re.match(
                r"^(?=.{1,253}$)([a-zA-Z0-9-]{1,63}\.)*[a-zA-Z]{2,63}$",
                value,
            ):
                return value

    raise vol.Invalid(f"Invalid IP or hostname: {value}")


def extract_ip_from_addresses(addresses: list[bytes | str]) -> str | None:
    """Return the first valid normalized IP from a list of addresses."""
    for addr in addresses or []:
        try:
            return normalize_address(addr)
        except vol.Invalid:
            continue
    return None


async def find_brother_printer(hass, model_name: str, timeout: int = 10) -> str | None:
    """Use Home Assistant's zeroconf instance to find a Brother printer by model name."""
    ip: str | None = None
    stop_event = asyncio.Event()

    def _on_service_add(zeroconf, service_type: str, name: str, *args, **kwargs):
        nonlocal ip
        if model_name not in name:
            return
        info = zeroconf.get_service_info(service_type, name)
        if info and info.addresses:
            ip = extract_ip_from_addresses(info.addresses)
            if ip:
                hass.loop.call_soon_threadsafe(stop_event.set)

    # Use HA’s shared Zeroconf instance
    zc = await ha_zeroconf.async_get_instance(hass)
    browser = ServiceBrowser(zc, "_printer._tcp.local.", handlers=[_on_service_add])

    try:
        await asyncio.wait_for(stop_event.wait(), timeout)
    except asyncio.TimeoutError:
        pass
    finally:
        browser.cancel()  # Clean up the browser

    return ip


class BrotherScannerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Brother DCP-1610W."""

    VERSION = 1

    async def _async_create_entry_for_ip(self, user_input_ip: str):
        """Resolve IP and create config entry."""
        # Normalize user input (IP or hostname)
        normalized = normalize_address(user_input_ip)

        # Resolve to IP if hostname
        try:
            ip = str(socket.gethostbyname(normalized))
        except OSError:
            ip = normalized  # Already an IP, fallback

        # Use IP as unique ID
        await self.async_set_unique_id(ip)
        self._abort_if_unique_id_configured()

        # Store user input (hostname or IP) for display, but IP remains unique ID
        return self.async_create_entry(
            title=f"{MANUFACTURER} {MODEL} Scanner ({user_input_ip})",
            data={"ip": ip, "hostname": user_input_ip},
        )

    def is_already_configured(self, ip: str | None) -> bool:
        """Return True if a printer with IP is already configured."""
        for entry in self._async_current_entries():
            if ip and entry.data.get("ip") == ip:
                return True
        return False

    async def async_step_user(self, user_input=None):
        """Manual configuration or auto-detection."""
        if user_input is not None:
            return await self._async_create_entry_for_ip(user_input["ip"])

        ip = await find_brother_printer(self.hass, MODEL)
        if ip:
            _LOGGER.info("Auto-detected Brother printer at %s", ip)
        else:
            _LOGGER.warning("No Brother printer found, leaving IP empty")

        self._discovered_ip = ip

        return await self._show_confirm_form(step_id="user")

    async def async_step_zeroconf(self, discovery_info):
        """Handle zeroconf discovery of Brother DCP-1610W."""
        model = discovery_info.properties.get("ty", "")

        if MODEL not in model:
            return self.async_abort(reason="not_supported")

        # Extract first valid IP (IPv4 or IPv6)
        ip = extract_ip_from_addresses(discovery_info.addresses)
        if ip is None:
            ip = discovery_info.host  # fallback

        if self.is_already_configured(ip):
            _LOGGER.info("Printer %s already configured, skipping discovery", ip)
            return self.async_abort(reason="already_configured")

        # Save for the confirm step
        self._discovered_ip = ip

        # Forward to zeroconf_confirm step
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input=None):
        return await self._show_confirm_form(
            step_id="zeroconf_confirm", user_input=user_input
        )

    async def _show_confirm_form(self, step_id: str, user_input=None):
        if user_input is not None:
            return await self._async_create_entry_for_ip(user_input["ip"])

        ip = getattr(self, "_discovered_ip", "") or ""

        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema({vol.Required("ip", default=ip): str}),
            description_placeholders={
                "host": ip,
                "manufacturer": MANUFACTURER,
                "model": MODEL,
            },
        )
