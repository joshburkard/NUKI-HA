"""
Nuki Smart Lock Switch Platform
Provides configuration switches for controllable settings
"""
from datetime import datetime
import logging
from typing import Any, Dict, Optional

from homeassistant.components.switch import SwitchEntity
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
    """Set up Nuki switches from config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    api = data["api"]
    smartlocks = data["smartlocks"]
    
    entities = []
    
    # Create configuration switches for each smartlock
    for smartlock in smartlocks:
        smartlock_id = smartlock["smartlockId"]
        smartlock_name = smartlock.get('name', 'Unknown Lock')
        
        # Auto Unlatch Switch
        entities.append(
            NukiAutoUnlatchSwitch(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        # LED Enabled Switch
        entities.append(
            NukiLEDEnabledSwitch(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        # Button Enabled Switch
        entities.append(
            NukiButtonEnabledSwitch(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        # Pairing Enabled Switch
        entities.append(
            NukiPairingEnabledSwitch(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        # Single Lock Switch
        entities.append(
            NukiSingleLockSwitch(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )

        # Advanced Configuration Switches
        entities.append(
            NukiAutoLockAdvancedSwitch(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        entities.append(
            NukiAutoUpdateEnabledSwitch(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        entities.append(
            NukiAutomaticBatteryDetectionSwitch(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        entities.append(
            NukiDetachedCylinderSwitch(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        entities.append(
            NukiSlowSpeedNightModeSwitch(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
    
    if entities:
        async_add_entities(entities, True)
        _LOGGER.info("Successfully set up %d Nuki switch(es)", len(entities))


class NukiConfigSwitchBase(SwitchEntity):
    """Base class for Nuki configuration switches."""
    
    def __init__(
        self,
        api,
        smartlock_id: int,
        smartlock_name: str,
        config_entry: ConfigEntry,
        switch_type: str,
        config_key: str,
        display_name: str,
    ):
        """Initialize the configuration switch."""
        self._api = api
        self._smartlock_id = smartlock_id
        self._smartlock_name = smartlock_name
        self._config_entry = config_entry
        self._switch_type = switch_type
        self._config_key = config_key
        
        # Entity properties
        self._attr_name = f"{smartlock_name} {display_name}"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_{switch_type}"
        self._attr_is_on = None
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
            sw_version=None,
            via_device=None,
        )
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        return {
            "smartlock_id": self._smartlock_id,
            "config_key": self._config_key,
            "last_update": self._last_update,
        }
    
    @property 
    def _enhanced_logging(self) -> bool:
        """Check if enhanced logging is enabled."""
        return self._config_entry.options.get("enable_enhanced_logging", False)

    async def async_update(self) -> None:
        """Update the switch state."""
        try:
            # Get full smartlock data
            data = await self._api.get_smartlock_full_data(self._smartlock_id)
            config = data.get("config", {})
            
            self._attr_is_on = bool(config.get(self._config_key, False))
            self._attr_available = True
            self._last_update = datetime.now().isoformat()
            
            if self._enhanced_logging:
                _LOGGER.debug("Config switch %s update: %s = %s", 
                            self._config_key, self._attr_name, self._attr_is_on)
            
        except Exception as ex:
            _LOGGER.error("Error updating config switch %s: %s", self._attr_name, ex)
            self._attr_available = False
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._update_config(True)
    
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._update_config(False)
    
    async def _update_config(self, value: bool) -> None:
        """Update the configuration setting."""
        try:
            # Get current config
            data = await self._api.get_smartlock_full_data(self._smartlock_id)
            current_config = data.get("config", {})
            
            # Create updated config with only the fields we can modify
            updated_config = {
                "name": current_config.get("name", self._smartlock_name),
                "latitude": current_config.get("latitude", 0),
                "longitude": current_config.get("longitude", 0),
                "autoUnlatch": current_config.get("autoUnlatch", False),
                "liftUpHandle": current_config.get("liftUpHandle", False),
                "pairingEnabled": current_config.get("pairingEnabled", True),
                "buttonEnabled": current_config.get("buttonEnabled", True),
                "ledEnabled": current_config.get("ledEnabled", True),
                "ledBrightness": current_config.get("ledBrightness", 3),
                "timezoneOffset": current_config.get("timezoneOffset", 0),
                "daylightSavingMode": current_config.get("daylightSavingMode", 0),
                "singleLock": current_config.get("singleLock", False),
                "advertisingMode": current_config.get("advertisingMode", 0),
                "timezoneId": current_config.get("timezoneId", 37),
            }
            
            # Update the specific setting
            updated_config[self._config_key] = value
            
            # Send the update
            result = await self._api.update_smartlock_config(self._smartlock_id, updated_config)
            
            if self._enhanced_logging:
                _LOGGER.debug("Config update result for %s: %s", self._config_key, result)
            
            # Update local state
            self._attr_is_on = value
            
            _LOGGER.info("Successfully updated %s to %s", self._attr_name, value)
            
        except Exception as ex:
            _LOGGER.error("Error updating config %s: %s", self._attr_name, ex)
            # Refresh state to get current value
            await self.async_update()


class NukiAutoUnlatchSwitch(NukiConfigSwitchBase):
    """Switch to control auto unlatch setting."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the auto unlatch switch."""
        super().__init__(
            api=api,
            smartlock_id=smartlock_id,
            smartlock_name=smartlock_name,
            config_entry=config_entry,
            switch_type="auto_unlatch_config",
            config_key="autoUnlatch",
            display_name="Auto Unlatch",
        )
    
    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:door-open" if self._attr_is_on else "mdi:door-closed-lock"


class NukiLEDEnabledSwitch(NukiConfigSwitchBase):
    """Switch to control LED enabled setting."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the LED enabled switch."""
        super().__init__(
            api=api,
            smartlock_id=smartlock_id,
            smartlock_name=smartlock_name,
            config_entry=config_entry,
            switch_type="led_enabled_config",
            config_key="ledEnabled",
            display_name="LED Enabled",
        )
    
    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:led-on" if self._attr_is_on else "mdi:led-off"


class NukiButtonEnabledSwitch(NukiConfigSwitchBase):
    """Switch to control button enabled setting."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the button enabled switch."""
        super().__init__(
            api=api,
            smartlock_id=smartlock_id,
            smartlock_name=smartlock_name,
            config_entry=config_entry,
            switch_type="button_enabled_config",
            config_key="buttonEnabled",
            display_name="Button Enabled",
        )
    
    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:gesture-tap-button" if self._attr_is_on else "mdi:button-pointer"


class NukiPairingEnabledSwitch(NukiConfigSwitchBase):
    """Switch to control pairing enabled setting."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the pairing enabled switch."""
        super().__init__(
            api=api,
            smartlock_id=smartlock_id,
            smartlock_name=smartlock_name,
            config_entry=config_entry,
            switch_type="pairing_enabled_config",
            config_key="pairingEnabled",
            display_name="Pairing Enabled",
        )
    
    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:bluetooth-connect" if self._attr_is_on else "mdi:bluetooth-off"


class NukiSingleLockSwitch(NukiConfigSwitchBase):
    """Switch to control single lock setting."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the single lock switch."""
        super().__init__(
            api=api,
            smartlock_id=smartlock_id,
            smartlock_name=smartlock_name,
            config_entry=config_entry,
            switch_type="single_lock_config",
            config_key="singleLock",
            display_name="Single Lock",
        )
    
    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:lock" if self._attr_is_on else "mdi:lock-multiple"

class NukiAdvancedConfigSwitchBase(SwitchEntity):
    """Base class for Nuki advanced configuration switches."""
    
    def __init__(
        self,
        api,
        smartlock_id: int,
        smartlock_name: str,
        config_entry: ConfigEntry,
        switch_type: str,
        config_key: str,
        display_name: str,
    ):
        """Initialize the advanced configuration switch."""
        self._api = api
        self._smartlock_id = smartlock_id
        self._smartlock_name = smartlock_name
        self._config_entry = config_entry
        self._switch_type = switch_type
        self._config_key = config_key
        
        # Entity properties
        self._attr_name = f"{smartlock_name} {display_name}"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_{switch_type}"
        self._attr_is_on = None
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
            sw_version=None,
            via_device=None,
        )
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        return {
            "smartlock_id": self._smartlock_id,
            "config_key": self._config_key,
            "last_update": self._last_update,
            "config_type": "advanced",
        }
    
    @property 
    def _enhanced_logging(self) -> bool:
        """Check if enhanced logging is enabled."""
        return self._config_entry.options.get("enable_enhanced_logging", False)

    async def async_update(self) -> None:
        """Update the switch state."""
        try:
            # Get full smartlock data
            data = await self._api.get_smartlock_full_data(self._smartlock_id)
            advanced_config = data.get("advancedConfig", {})
            
            self._attr_is_on = bool(advanced_config.get(self._config_key, False))
            self._attr_available = True
            self._last_update = datetime.now().isoformat()
            
            if self._enhanced_logging:
                _LOGGER.debug("Advanced config switch %s update: %s = %s", 
                            self._config_key, self._attr_name, self._attr_is_on)
            
        except Exception as ex:
            _LOGGER.error("Error updating advanced config switch %s: %s", self._attr_name, ex)
            self._attr_available = False
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._update_advanced_config(True)
    
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._update_advanced_config(False)
    
    async def _update_advanced_config(self, value: bool) -> None:
        """Update the advanced configuration setting."""
        try:
            # Get current advanced config
            data = await self._api.get_smartlock_full_data(self._smartlock_id)
            current_advanced_config = data.get("advancedConfig", {})
            
            # Create updated config with current values
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
            
            # Update the specific setting
            updated_config[self._config_key] = value
            
            # Send the update
            result = await self._api.update_smartlock_advanced_config(self._smartlock_id, updated_config)
            
            if self._enhanced_logging:
                _LOGGER.debug("Advanced config update result for %s: %s", self._config_key, result)
            
            # Update local state
            self._attr_is_on = value
            
            _LOGGER.info("Successfully updated advanced %s to %s", self._attr_name, value)
            
        except Exception as ex:
            _LOGGER.error("Error updating advanced config %s: %s", self._attr_name, ex)
            # Refresh state to get current value
            await self.async_update()


class NukiAutoLockAdvancedSwitch(NukiAdvancedConfigSwitchBase):
    """Switch to control advanced auto lock setting."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the advanced auto lock switch."""
        super().__init__(
            api=api,
            smartlock_id=smartlock_id,
            smartlock_name=smartlock_name,
            config_entry=config_entry,
            switch_type="auto_lock_advanced",
            config_key="autoLock",
            display_name="Auto Lock (Advanced)",
        )
    
    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:timer-lock" if self._attr_is_on else "mdi:timer-lock-outline"


class NukiAutoUpdateEnabledSwitch(NukiAdvancedConfigSwitchBase):
    """Switch to control auto update setting."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the auto update enabled switch."""
        super().__init__(
            api=api,
            smartlock_id=smartlock_id,
            smartlock_name=smartlock_name,
            config_entry=config_entry,
            switch_type="auto_update_enabled",
            config_key="autoUpdateEnabled",
            display_name="Auto Update",
        )
    
    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:update" if self._attr_is_on else "mdi:update-lock"


class NukiAutomaticBatteryDetectionSwitch(NukiAdvancedConfigSwitchBase):
    """Switch to control automatic battery detection setting."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the automatic battery detection switch."""
        super().__init__(
            api=api,
            smartlock_id=smartlock_id,
            smartlock_name=smartlock_name,
            config_entry=config_entry,
            switch_type="automatic_battery_detection",
            config_key="automaticBatteryTypeDetection",
            display_name="Auto Battery Detection",
        )
    
    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:battery-sync" if self._attr_is_on else "mdi:battery-sync-outline"


class NukiDetachedCylinderSwitch(NukiAdvancedConfigSwitchBase):
    """Switch to control detached cylinder setting."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the detached cylinder switch."""
        super().__init__(
            api=api,
            smartlock_id=smartlock_id,
            smartlock_name=smartlock_name,
            config_entry=config_entry,
            switch_type="detached_cylinder",
            config_key="detachedCylinder",
            display_name="Detached Cylinder",
        )
    
    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:cylinder" if self._attr_is_on else "mdi:cylinder-off"


class NukiSlowSpeedNightModeSwitch(NukiAdvancedConfigSwitchBase):
    """Switch to control slow speed during night mode setting."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the slow speed night mode switch."""
        super().__init__(
            api=api,
            smartlock_id=smartlock_id,
            smartlock_name=smartlock_name,
            config_entry=config_entry,
            switch_type="slow_speed_night_mode",
            config_key="enableSlowSpeedDuringNightmode",
            display_name="Slow Speed Night Mode",
        )
    
    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:speedometer-slow" if self._attr_is_on else "mdi:speedometer"