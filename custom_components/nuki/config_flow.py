"""Config flow for Nuki Smart Lock integration."""
import logging
from typing import Any, Dict, Optional

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL
from .lock import NukiAPI

_LOGGER = logging.getLogger(__name__)

class NukiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nuki Smart Lock."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate the API key
            api_key = user_input[CONF_API_KEY]
            
            # Test the API connection
            session = async_get_clientsession(self.hass)
            api = NukiAPI(session, api_key)
            
            try:
                # Test connection and get smartlocks
                if await api.test_connection():
                    smartlocks = await api.get_smartlocks()
                    if smartlocks:
                        # Also test keypad discovery
                        keypad_count = 0
                        for smartlock in smartlocks:
                            try:
                                keypads = await api.get_smartlock_auth(smartlock["smartlockId"])
                                if keypads:
                                    keypad_count += len([k for k in keypads if k.get("type") == 13])
                            except:
                                pass  # Non-critical, keypads are optional
                        
                        # Create a unique ID based on the first smartlock
                        await self.async_set_unique_id(f"nuki_{smartlocks[0]['smartlockId']}")
                        self._abort_if_unique_id_configured()
                        
                        title = user_input.get(CONF_NAME, "Nuki Smart Lock")
                        if len(smartlocks) > 1:
                            title = f"Nuki ({len(smartlocks)} locks"
                            if keypad_count > 0:
                                title += f", {keypad_count} keypads"
                            title += ")"
                        elif keypad_count > 0:
                            title += f" (+{keypad_count} keypad{'s' if keypad_count > 1 else ''})"
                        
                        return self.async_create_entry(
                            title=title,
                            data=user_input,
                        )
                    else:
                        errors["base"] = "no_smartlocks"
                else:
                    errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during API test")
                errors["base"] = "cannot_connect"

        # Show the form
        data_schema = vol.Schema({
            vol.Required(CONF_API_KEY): str,
            vol.Optional(CONF_NAME, default="Nuki Smart Lock"): str,
            vol.Optional(CONF_SCAN_INTERVAL, default=30): vol.All(
                vol.Coerce(int), vol.Range(min=10, max=300)
            ),
        })
        
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return NukiOptionsFlowHandler(config_entry)


class NukiOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Nuki Smart Lock."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema({
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(CONF_SCAN_INTERVAL, 30),
            ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
            vol.Optional(
                "fingerprint_detection_window",
                default=self.config_entry.options.get("fingerprint_detection_window", 120),
            ): vol.All(vol.Coerce(int), vol.Range(min=30, max=600)),
            vol.Optional(
                "enable_enhanced_logging",
                default=self.config_entry.options.get("enable_enhanced_logging", False),
            ): bool,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )