"""
Nuki Smart Lock Integration for Home Assistant.

This integration provides support for Nuki Smart Lock with Keypad,
including lock control, keypad event detection, and automation triggers.
"""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Nuki integration."""
    hass.data.setdefault(DOMAIN, {})
    
    # Register services
    await async_setup_services(hass)
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nuki from a config entry."""
    from .lock import NukiAPI
    from homeassistant.helpers.aiohttp_client import async_get_clientsession
    
    hass.data.setdefault(DOMAIN, {})
    
    # Create API client
    session = async_get_clientsession(hass)
    api = NukiAPI(session, entry.data[CONF_API_KEY])
    
    # Test connection
    try:
        if not await api.test_connection():
            raise ConfigEntryNotReady("Failed to connect to Nuki API")
        
        smartlocks = await api.get_smartlocks()
        if not smartlocks:
            raise ConfigEntryNotReady("No smart locks found")
            
    except Exception as ex:
        _LOGGER.error("Error connecting to Nuki API: %s", ex)
        raise ConfigEntryNotReady(f"Error connecting to Nuki API: {ex}") from ex
    
    # Store config entry data
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "smartlocks": smartlocks,
        "config_entry": entry,
    }
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Setup entry update listener for options
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Nuki integration."""
    
    async def handle_debug_last_access(call: ServiceCall) -> None:
        """Debug service to show last access detection logic."""
        try:
            _LOGGER.info("=== NUKI DEBUG SERVICE CALLED ===")
            
            # Find the API client for any entry
            api = None
            smartlocks = None
            
            for entry_data in hass.data[DOMAIN].values():
                if isinstance(entry_data, dict) and "api" in entry_data:
                    api = entry_data["api"]
                    smartlocks = entry_data["smartlocks"]
                    break
            
            if not api:
                _LOGGER.error("No Nuki API client found in hass.data")
                return
            
            if not smartlocks:
                _LOGGER.error("No smartlocks found")
                return
                
            smartlock_id = smartlocks[0]["smartlockId"]
            _LOGGER.info("Using smartlock ID: %s", smartlock_id)
            
            # Get recent logs
            logs = await api.get_smartlock_logs(smartlock_id, limit=20)
            _LOGGER.info("Retrieved %d log entries from API", len(logs))
            
            # Show first 5 entries with keypad detection
            for i, log_entry in enumerate(logs[:5]):
                trigger = log_entry.get("trigger")
                source = log_entry.get("source", 0)
                user_name = log_entry.get("name", "")
                state = log_entry.get("state", 0)
                date = log_entry.get("date", "")
                
                is_keypad = trigger == 255 and source in [1, 2]
                
                _LOGGER.info("Entry %d: trigger=%s, source=%s, name='%s', state=%s, date=%s, IS_KEYPAD=%s", 
                           i, trigger, source, user_name, state, date, is_keypad)
                
                if is_keypad:
                    _LOGGER.info("  ^^ FIRST KEYPAD ENTRY - This should be the last access!")
                    _LOGGER.info("  Expected: User='%s', Method='%s', Time='%s'", 
                               user_name, 
                               "Fingerprint" if source == 2 else "PIN Code",
                               date)
                    break
            
        except Exception as ex:
            _LOGGER.error("Error in debug service: %s", ex)
            import traceback
            _LOGGER.error("Traceback: %s", traceback.format_exc())
    
    # Register debug service
    hass.services.async_register(DOMAIN, "debug_last_access", handle_debug_last_access)
    
    _LOGGER.info("Nuki debug service registered")