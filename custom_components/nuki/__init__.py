"""
Nuki Smart Lock Ultra Integration for Home Assistant.

This integration provides support for Nuki Smart Lock Ultra with Keypad,
including lock control, keypad event detection, and automation triggers.
"""
import asyncio
import logging
from typing import Any, Dict

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "nuki"
PLATFORMS = [Platform.LOCK]

# Configuration schema
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional("scan_interval", default=30): cv.positive_int,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Nuki integration."""
    hass.data.setdefault(DOMAIN, {})
    
    # Register services
    await async_setup_services(hass)
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nuki from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Store config entry data
    hass.data[DOMAIN][entry.entry_id] = {
        "api_key": entry.data[CONF_API_KEY],
        "config_entry": entry,
    }
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Nuki integration."""
    
    async def handle_unlatch(call: ServiceCall) -> None:
        """Handle unlatch service call."""
        entity_id = call.data.get("entity_id")
        if not entity_id:
            _LOGGER.error("No entity_id provided for unlatch service")
            return
        
        # Find the entity in the lock platform
        entity = None
        for platform in hass.data.get("entity_platform", {}).values():
            if platform.domain == "lock":
                for ent in platform.entities.values():
                    if ent.entity_id == entity_id and hasattr(ent, "async_unlatch"):
                        entity = ent
                        break
        
        if entity:
            try:
                await entity.async_unlatch()
                _LOGGER.info("Unlatch command sent to %s", entity_id)
            except Exception as ex:
                _LOGGER.error("Error executing unlatch for %s: %s", entity_id, ex)
        else:
            _LOGGER.error("Entity %s not found or does not support unlatch", entity_id)
    
    async def handle_lock_n_go(call: ServiceCall) -> None:
        """Handle lock n go service call."""
        entity_id = call.data.get("entity_id")
        if not entity_id:
            _LOGGER.error("No entity_id provided for lock_n_go service")
            return
        
        # Find the entity in the lock platform
        entity = None
        for platform in hass.data.get("entity_platform", {}).values():
            if platform.domain == "lock":
                for ent in platform.entities.values():
                    if ent.entity_id == entity_id and hasattr(ent, "async_lock_n_go"):
                        entity = ent
                        break
        
        if entity:
            try:
                await entity.async_lock_n_go()
                _LOGGER.info("Lock n Go command sent to %s", entity_id)
            except Exception as ex:
                _LOGGER.error("Error executing lock_n_go for %s: %s", entity_id, ex)
        else:
            _LOGGER.error("Entity %s not found or does not support lock_n_go", entity_id)
    
    # Service schemas
    SERVICE_UNLATCH_SCHEMA = vol.Schema({
        vol.Required("entity_id"): cv.entity_id,
    })
    
    SERVICE_LOCK_N_GO_SCHEMA = vol.Schema({
        vol.Required("entity_id"): cv.entity_id,
    })
    
    # Register services only if they don't exist
    if not hass.services.has_service(DOMAIN, "unlatch"):
        hass.services.async_register(
            DOMAIN, 
            "unlatch", 
            handle_unlatch,
            schema=SERVICE_UNLATCH_SCHEMA
        )
    
    if not hass.services.has_service(DOMAIN, "lock_n_go"):
        hass.services.async_register(
            DOMAIN, 
            "lock_n_go", 
            handle_lock_n_go,
            schema=SERVICE_LOCK_N_GO_SCHEMA
        )
    
    _LOGGER.info("Nuki services registered: unlatch, lock_n_go")