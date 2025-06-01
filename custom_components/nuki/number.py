"""
Nuki Smart Lock Number Platform
Provides number entities for configurable numeric settings
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from homeassistant.components.number import NumberEntity, NumberMode
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
    """Set up Nuki number entities from config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    api = data["api"]
    smartlocks = data["smartlocks"]
    
    entities = []
    
    # Create number entities for each smartlock
    for smartlock in smartlocks:
        smartlock_id = smartlock["smartlockId"]
        smartlock_name = smartlock.get('name', 'Unknown Lock')
        
        # LED Brightness Number
        entities.append(
            NukiLEDBrightnessNumber(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        # Advanced Configuration Numbers
        entities.append(
            NukiAutoLockTimeoutAdvancedNumber(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        entities.append(
            NukiLockNGoTimeoutNumber(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        entities.append(
            NukiUnlatchDurationNumber(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
    
    if entities:
        async_add_entities(entities, True)
        _LOGGER.info("Successfully set up %d Nuki number entit(y/ies)", len(entities))


class NukiConfigNumberBase(NumberEntity):
    """Base class for Nuki configuration number entities."""
    
    def __init__(
        self,
        api,
        smartlock_id: int,
        smartlock_name: str,
        config_entry: ConfigEntry,
        number_type: str,
        config_key: str,
        display_name: str,
        min_value: float,
        max_value: float,
        step: float = 1,
        unit: str = None,
    ):
        """Initialize the configuration number entity."""
        self._api = api
        self._smartlock_id = smartlock_id
        self._smartlock_name = smartlock_name
        self._config_entry = config_entry
        self._number_type = number_type
        self._config_key = config_key
        
        # Entity properties
        self._attr_name = f"{smartlock_name} {display_name}"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_{number_type}"
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_mode = NumberMode.SLIDER
        
        if unit:
            self._attr_native_unit_of_measurement = unit
        
        # State tracking
        self._attr_native_value = None
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
        """Update the number entity state."""
        try:
            # Get full smartlock data
            data = await self._api.get_smartlock_full_data(self._smartlock_id)
            config = data.get("config", {})
            
            self._attr_native_value = config.get(self._config_key, self._attr_native_min_value)
            self._attr_available = True
            self._last_update = datetime.now().isoformat()
            
            if self._enhanced_logging:
                _LOGGER.debug("Config number %s update: %s = %s", 
                            self._config_key, self._attr_name, self._attr_native_value)
            
        except Exception as ex:
            _LOGGER.error("Error updating config number %s: %s", self._attr_name, ex)
            self._attr_available = False
    
    async def async_set_native_value(self, value: float) -> None:
        """Update the configuration setting."""
        try:
            # Convert to appropriate type
            if self._attr_native_step == 1:
                value = int(value)
            
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
            self._attr_native_value = value
            
            _LOGGER.info("Successfully updated %s to %s", self._attr_name, value)
            
        except Exception as ex:
            _LOGGER.error("Error updating config %s: %s", self._attr_name, ex)
            # Refresh state to get current value
            await self.async_update()


class NukiLEDBrightnessNumber(NukiConfigNumberBase):
    """Number entity to control LED brightness."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the LED brightness number entity."""
        super().__init__(
            api=api,
            smartlock_id=smartlock_id,
            smartlock_name=smartlock_name,
            config_entry=config_entry,
            number_type="led_brightness_config",
            config_key="ledBrightness",
            display_name="LED Brightness",
            min_value=0,
            max_value=5,
            step=1,
        )
    
    @property
    def icon(self) -> str:
        """Return the icon for the number entity."""
        if self._attr_native_value and self._attr_native_value > 0:
            if self._attr_native_value <= 1:
                return "mdi:brightness-2"
            elif self._attr_native_value <= 3:
                return "mdi:brightness-5"
            else:
                return "mdi:brightness-7"
        else:
            return "mdi:brightness-1"


class NukiAdvancedConfigNumberBase(NumberEntity):
    """Base class for Nuki advanced configuration number entities."""
    
    def __init__(
        self,
        api,
        smartlock_id: int,
        smartlock_name: str,
        config_entry: ConfigEntry,
        number_type: str,
        config_key: str,
        display_name: str,
        min_value: float,
        max_value: float,
        step: float = 1,
        unit: str = None,
    ):
        """Initialize the advanced configuration number entity."""
        self._api = api
        self._smartlock_id = smartlock_id
        self._smartlock_name = smartlock_name
        self._config_entry = config_entry
        self._number_type = number_type
        self._config_key = config_key
        
        # Entity properties
        self._attr_name = f"{smartlock_name} {display_name}"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_{number_type}"
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_mode = NumberMode.SLIDER
        
        if unit:
            self._attr_native_unit_of_measurement = unit
        
        # State tracking
        self._attr_native_value = None
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
        """Update the number entity state."""
        try:
            # Get full smartlock data
            data = await self._api.get_smartlock_full_data(self._smartlock_id)
            advanced_config = data.get("advancedConfig", {})
            
            self._attr_native_value = advanced_config.get(self._config_key, self._attr_native_min_value)
            self._attr_available = True
            self._last_update = datetime.now().isoformat()
            
            if self._enhanced_logging:
                _LOGGER.debug("Advanced config number %s update: %s = %s", 
                            self._config_key, self._attr_name, self._attr_native_value)
            
        except Exception as ex:
            _LOGGER.error("Error updating advanced config number %s: %s", self._attr_name, ex)
            self._attr_available = False
    
    async def async_set_native_value(self, value: float) -> None:
        """Update the advanced configuration setting."""
        try:
            # Convert to appropriate type
            if self._attr_native_step == 1:
                value = int(value)
            
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
            self._attr_native_value = value
            
            _LOGGER.info("Successfully updated advanced %s to %s", self._attr_name, value)
            
        except Exception as ex:
            _LOGGER.error("Error updating advanced config %s: %s", self._attr_name, ex)
            # Refresh state to get current value
            await self.async_update()


class NukiAutoLockTimeoutAdvancedNumber(NukiAdvancedConfigNumberBase):
    """Number entity to control advanced auto lock timeout."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the advanced auto lock timeout number entity."""
        super().__init__(
            api=api,
            smartlock_id=smartlock_id,
            smartlock_name=smartlock_name,
            config_entry=config_entry,
            number_type="auto_lock_timeout_advanced",
            config_key="autoLockTimeout",
            display_name="Auto Lock Timeout (Advanced)",
            min_value=2,
            max_value=3600,  # 1 hour max
            step=1,
            unit="s",
        )
    
    @property
    def icon(self) -> str:
        """Return the icon for the number entity."""
        return "mdi:timer-lock-outline"


class NukiLockNGoTimeoutNumber(NukiAdvancedConfigNumberBase):
    """Number entity to control Lock 'n' Go timeout."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the Lock 'n' Go timeout number entity."""
        super().__init__(
            api=api,
            smartlock_id=smartlock_id,
            smartlock_name=smartlock_name,
            config_entry=config_entry,
            number_type="lng_timeout",
            config_key="lngTimeout",
            display_name="Lock 'n' Go Timeout",
            min_value=5,
            max_value=60,
            step=1,
            unit="s",
        )
    
    @property
    def icon(self) -> str:
        """Return the icon for the number entity."""
        return "mdi:timer-lock"


class NukiUnlatchDurationNumber(NukiAdvancedConfigNumberBase):
    """Number entity to control unlatch duration."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the unlatch duration number entity."""
        super().__init__(
            api=api,
            smartlock_id=smartlock_id,
            smartlock_name=smartlock_name,
            config_entry=config_entry,
            number_type="unlatch_duration",
            config_key="unlatchDuration",
            display_name="Unlatch Duration",
            min_value=1,
            max_value=30,
            step=1,
            unit="s",
        )
        
        # Override mode for this specific entity - use box for discrete values
        self._attr_mode = NumberMode.BOX
        
        # Valid values according to API: 1, 3, 5, 7, 10, 15, 20, 30
        self._valid_values = [1, 3, 5, 7, 10, 15, 20, 30]
    
    async def async_set_native_value(self, value: float) -> None:
        """Validate and update the unlatch duration setting."""
        value = int(value)
        
        # Find the closest valid value
        closest_valid = min(self._valid_values, key=lambda x: abs(x - value))
        
        if value != closest_valid:
            _LOGGER.warning("Unlatch duration %s is not valid. Using closest valid value: %s", 
                          value, closest_valid)
            value = closest_valid
        
        # Call parent method with validated value
        await super().async_set_native_value(value)
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        attrs = super().extra_state_attributes
        attrs["valid_values"] = self._valid_values
        return attrs
    
    @property
    def icon(self) -> str:
        """Return the icon for the number entity."""
        return "mdi:door-open"