"""
Nuki Smart Lock Select Platform
Provides dropdown selections for configurable actions and settings
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nuki select entities from config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    api = data["api"]
    smartlocks = data["smartlocks"]
    
    entities = []
    
    # Create select entities for each smartlock
    for smartlock in smartlocks:
        smartlock_id = smartlock["smartlockId"]
        smartlock_name = smartlock.get('name', 'Unknown Lock')
        
        # Single Button Press Action
        entities.append(
            NukiButtonActionSelect(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
                action_type="single",
                config_key="singleButtonPressAction",
            )
        )
        
        # Double Button Press Action
        entities.append(
            NukiButtonActionSelect(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
                action_type="double",
                config_key="doubleButtonPressAction",
            )
        )
        
        # Motor Speed Select
        entities.append(
            NukiMotorSpeedSelect(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        # Battery Type Select - REMOVED: Converted to read-only sensor for safety
    
    if entities:
        async_add_entities(entities, True)
        _LOGGER.info("Successfully set up %d Nuki select entit(y/ies)", len(entities))


class NukiButtonActionSelect(SelectEntity):
    """Select entity for button press actions."""
    
    def __init__(
        self,
        api,
        smartlock_id: int,
        smartlock_name: str,
        config_entry: ConfigEntry,
        action_type: str,  # "single" or "double"
        config_key: str,
    ):
        """Initialize the button action select entity."""
        self._api = api
        self._smartlock_id = smartlock_id
        self._smartlock_name = smartlock_name
        self._config_entry = config_entry
        self._action_type = action_type
        self._config_key = config_key
        
        # Entity properties
        action_display = "Single" if action_type == "single" else "Double"
        self._attr_name = f"{smartlock_name} {action_display} Button Press Action"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_{action_type}_button_action"
        
        # Options mapping
        self._action_options = {
            0: "No Action",
            1: "Intelligent",
            2: "Unlock",
            3: "Lock", 
            4: "Unlatch",
            5: "Lock 'n' Go",
            6: "Show Status"
        }
        
        self._attr_options = list(self._action_options.values())
        self._attr_current_option = None
        self._attr_available = True
        self._last_update = None
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._smartlock_id))},
            name=self._smartlock_name,
            manufacturer="Nuki",
            model="Smart Lock Ultra" if "Ultra" in self._smartlock_name else "Smart Lock",
        )
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        return {
            "smartlock_id": self._smartlock_id,
            "config_key": self._config_key,
            "action_type": self._action_type,
            "last_update": self._last_update,
        }
    
    @property 
    def _enhanced_logging(self) -> bool:
        """Check if enhanced logging is enabled."""
        return self._config_entry.options.get("enable_enhanced_logging", False)

    async def async_update(self) -> None:
        """Update the select entity state."""
        try:
            data = await self._api.get_smartlock_full_data(self._smartlock_id)
            advanced_config = data.get("advancedConfig", {})
            
            action_value = advanced_config.get(self._config_key, 0)
            self._attr_current_option = self._action_options.get(action_value, "No Action")
            self._attr_available = True
            self._last_update = datetime.now().isoformat()
            
            if self._enhanced_logging:
                _LOGGER.debug("Button action select %s update: %s = %s", 
                            self._config_key, self._attr_name, self._attr_current_option)
            
        except Exception as ex:
            _LOGGER.error("Error updating button action select %s: %s", self._attr_name, ex)
            self._attr_available = False
    
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        try:
            # Find the action value for the selected option
            action_value = None
            for value, name in self._action_options.items():
                if name == option:
                    action_value = value
                    break
            
            if action_value is None:
                _LOGGER.error("Invalid option selected: %s", option)
                return
            
            # Get current advanced config and update
            data = await self._api.get_smartlock_full_data(self._smartlock_id)
            current_advanced_config = data.get("advancedConfig", {})
            
            updated_config = {
                "lngTimeout": current_advanced_config.get("lngTimeout", 20),
                "singleButtonPressAction": current_advanced_config.get("singleButtonPressAction", 1),
                "doubleButtonPressAction": current_advanced_config.get("doubleButtonPressAction", 4),
                "automaticBatteryTypeDetection": current_advanced_config.get("automaticBatteryTypeDetection", True),
                "unlatchDuration": current_advanced_config.get("unlatchDuration", 3),
                "singleLockedPositionOffsetDegrees": current_advanced_config.get("singleLockedPositionOffsetDegrees", 0),
                "unlockedToLockedTransitionOffsetDegrees": current_advanced_config.get("unlockedToLockedTransitionOffsetDegrees", 0),
                "unlockedPositionOffsetDegrees": current_advanced_config.get("unlockedPositionOffsetDegrees", 0),
                "lockedPositionOffsetDegrees": current_advanced_config.get("lockedPositionOffsetDegrees", 0),
                "detachedCylinder": current_advanced_config.get("detachedCylinder", False),
                "batteryType": current_advanced_config.get("batteryType", 0),
                "autoLock": current_advanced_config.get("autoLock", False),
                "autoLockTimeout": current_advanced_config.get("autoLockTimeout", 300),
                "autoUpdateEnabled": current_advanced_config.get("autoUpdateEnabled", True),
                "motorSpeed": current_advanced_config.get("motorSpeed", 0),
                "enableSlowSpeedDuringNightmode": current_advanced_config.get("enableSlowSpeedDuringNightmode", True),
            }
            
            updated_config[self._config_key] = action_value
            
            result = await self._api.update_smartlock_advanced_config(self._smartlock_id, updated_config)
            
            if self._enhanced_logging:
                _LOGGER.debug("Advanced config update result for %s: %s", self._config_key, result)
            
            self._attr_current_option = option
            
            _LOGGER.info("Successfully updated %s to %s", self._attr_name, option)
            
        except Exception as ex:
            _LOGGER.error("Error updating button action %s: %s", self._attr_name, ex)
            await self.async_update()
    
    @property
    def icon(self) -> str:
        """Return the icon for the select entity."""
        if self._action_type == "single":
            return "mdi:gesture-tap"
        else:
            return "mdi:gesture-double-tap"


class NukiMotorSpeedSelect(SelectEntity):
    """Select entity for motor speed setting."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the motor speed select entity."""
        self._api = api
        self._smartlock_id = smartlock_id
        self._smartlock_name = smartlock_name
        self._config_entry = config_entry
        
        # Entity properties
        self._attr_name = f"{smartlock_name} Motor Speed"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_motor_speed"
        
        # Options mapping
        self._speed_options = {
            0: "Standard",
            1: "Fast",
            2: "Slow"
        }
        
        self._attr_options = list(self._speed_options.values())
        self._attr_current_option = None
        self._attr_available = True
        self._last_update = None
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._smartlock_id))},
            name=self._smartlock_name,
            manufacturer="Nuki",
            model="Smart Lock Ultra" if "Ultra" in self._smartlock_name else "Smart Lock",
        )
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        return {
            "smartlock_id": self._smartlock_id,
            "config_key": "motorSpeed",
            "last_update": self._last_update,
        }
    
    @property 
    def _enhanced_logging(self) -> bool:
        """Check if enhanced logging is enabled."""
        return self._config_entry.options.get("enable_enhanced_logging", False)

    async def async_update(self) -> None:
        """Update the select entity state."""
        try:
            data = await self._api.get_smartlock_full_data(self._smartlock_id)
            advanced_config = data.get("advancedConfig", {})
            
            speed_value = advanced_config.get("motorSpeed", 0)
            self._attr_current_option = self._speed_options.get(speed_value, "Standard")
            self._attr_available = True
            self._last_update = datetime.now().isoformat()
            
            if self._enhanced_logging:
                _LOGGER.debug("Motor speed select update: %s = %s", 
                            self._attr_name, self._attr_current_option)
            
        except Exception as ex:
            _LOGGER.error("Error updating motor speed select %s: %s", self._attr_name, ex)
            self._attr_available = False
    
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        try:
            # Find the speed value for the selected option
            speed_value = None
            for value, name in self._speed_options.items():
                if name == option:
                    speed_value = value
                    break
            
            if speed_value is None:
                _LOGGER.error("Invalid motor speed option selected: %s", option)
                return
            
            # Get current advanced config and update
            data = await self._api.get_smartlock_full_data(self._smartlock_id)
            current_advanced_config = data.get("advancedConfig", {})
            
            updated_config = {
                "lngTimeout": current_advanced_config.get("lngTimeout", 20),
                "singleButtonPressAction": current_advanced_config.get("singleButtonPressAction", 1),
                "doubleButtonPressAction": current_advanced_config.get("doubleButtonPressAction", 4),
                "automaticBatteryTypeDetection": current_advanced_config.get("automaticBatteryTypeDetection", True),
                "unlatchDuration": current_advanced_config.get("unlatchDuration", 3),
                "singleLockedPositionOffsetDegrees": current_advanced_config.get("singleLockedPositionOffsetDegrees", 0),
                "unlockedToLockedTransitionOffsetDegrees": current_advanced_config.get("unlockedToLockedTransitionOffsetDegrees", 0),
                "unlockedPositionOffsetDegrees": current_advanced_config.get("unlockedPositionOffsetDegrees", 0),
                "lockedPositionOffsetDegrees": current_advanced_config.get("lockedPositionOffsetDegrees", 0),
                "detachedCylinder": current_advanced_config.get("detachedCylinder", False),
                "batteryType": current_advanced_config.get("batteryType", 0),
                "autoLock": current_advanced_config.get("autoLock", False),
                "autoLockTimeout": current_advanced_config.get("autoLockTimeout", 300),
                "autoUpdateEnabled": current_advanced_config.get("autoUpdateEnabled", True),
                "motorSpeed": current_advanced_config.get("motorSpeed", 0),
                "enableSlowSpeedDuringNightmode": current_advanced_config.get("enableSlowSpeedDuringNightmode", True),
            }
            
            updated_config["motorSpeed"] = speed_value
            
            result = await self._api.update_smartlock_advanced_config(self._smartlock_id, updated_config)
            
            if self._enhanced_logging:
                _LOGGER.debug("Motor speed update result: %s", result)
            
            self._attr_current_option = option
            
            _LOGGER.info("Successfully updated %s to %s", self._attr_name, option)
            
        except Exception as ex:
            _LOGGER.error("Error updating motor speed %s: %s", self._attr_name, ex)
            await self.async_update()
    
    @property
    def icon(self) -> str:
        """Return the icon for the select entity."""
        if self._attr_current_option == "Fast":
            return "mdi:speedometer"
        elif self._attr_current_option == "Slow":
            return "mdi:speedometer-slow"
        else:
            return "mdi:speedometer-medium"


# Battery Type Select class removed for safety - converted to read-only sensor