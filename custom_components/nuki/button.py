"""
Nuki Smart Lock Button Platform
Provides action buttons for Smart Lock operations
"""
import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NUKI_ACTIONS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nuki buttons from config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    api = data["api"]
    smartlocks = data["smartlocks"]
    
    entities = []
    
    # Create buttons for each smartlock
    for smartlock in smartlocks:
        smartlock_id = smartlock["smartlockId"]
        smartlock_name = smartlock.get('name', 'Unknown Lock')
        
        # Create unlatch button
        entities.append(
            NukiUnlatchButton(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        # Create lock 'n' go button
        entities.append(
            NukiLockNGoButton(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        _LOGGER.info("Added action buttons for lock %s", smartlock_name)
    
    if entities:
        async_add_entities(entities, True)
        _LOGGER.info("Successfully set up %d Nuki button(s)", len(entities))


class NukiBaseButton(ButtonEntity):
    """Base class for Nuki action buttons."""
    
    def __init__(
        self,
        api,
        smartlock_id: int,
        smartlock_name: str,
        config_entry: ConfigEntry,
        button_type: str,
        action_name: str,
        nuki_action: int,
    ):
        """Initialize the button."""
        self._api = api
        self._smartlock_id = smartlock_id
        self._smartlock_name = smartlock_name
        self._config_entry = config_entry
        self._button_type = button_type
        self._action_name = action_name
        self._nuki_action = nuki_action
        
        # Entity properties
        self._attr_name = f"{smartlock_name} {action_name}"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_{button_type}"
        self._attr_available = True
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._smartlock_id))},
            name=self._smartlock_name,
            manufacturer="Nuki",
            model="Smart Lock Ultra" if "Ultra" in self._smartlock_name else "Smart Lock",
            sw_version=None,
            via_device=None,
        )
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {
            "smartlock_id": self._smartlock_id,
            "action_type": self._button_type,
            "nuki_action_code": self._nuki_action,
        }
    
    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            _LOGGER.info("Executing %s for lock %s", self._action_name, self._smartlock_name)
            
            # Send the action to the API
            result = await self._api.set_smartlock_action(self._smartlock_id, self._nuki_action)
            
            if self._enhanced_logging:
                _LOGGER.debug("API response for %s: %s", self._action_name, result)
            
            _LOGGER.info("Successfully executed %s for lock %s", self._action_name, self._smartlock_name)
            
        except Exception as ex:
            _LOGGER.error("Error executing %s for %s: %s", self._action_name, self._smartlock_name, ex)
            # Note: We don't raise the exception to avoid showing errors in UI for temporary issues
    
    @property 
    def _enhanced_logging(self) -> bool:
        """Check if enhanced logging is enabled."""
        return self._config_entry.options.get("enable_enhanced_logging", False)


class NukiUnlatchButton(NukiBaseButton):
    """Button to unlatch the Nuki Smart Lock."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the unlatch button."""
        super().__init__(
            api=api,
            smartlock_id=smartlock_id,
            smartlock_name=smartlock_name,
            config_entry=config_entry,
            button_type="unlatch",
            action_name="Unlatch",
            nuki_action=NUKI_ACTIONS["unlatch"],
        )
    
    @property
    def icon(self) -> str:
        """Return the icon for the button."""
        return "mdi:door-open"


class NukiLockNGoButton(NukiBaseButton):
    """Button to trigger Lock 'n' Go on the Nuki Smart Lock."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the lock 'n' go button."""
        super().__init__(
            api=api,
            smartlock_id=smartlock_id,
            smartlock_name=smartlock_name,
            config_entry=config_entry,
            button_type="lock_n_go",
            action_name="Lock 'n' Go",
            nuki_action=NUKI_ACTIONS["lock_n_go"],
        )
    
    @property
    def icon(self) -> str:
        """Return the icon for the button."""
        return "mdi:lock-smart"