"""
Nuki Smart Lock Binary Sensor Platform
Provides door state and connectivity sensors based on real API data
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    DEVICE_TYPE_SMARTLOCK,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nuki binary sensors from config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    api = data["api"]
    smartlocks = data["smartlocks"]
    
    entities = []
    
    # Create binary sensors for each smartlock
    for smartlock in smartlocks:
        smartlock_id = smartlock["smartlockId"]
        smartlock_name = smartlock.get('name', 'Unknown Lock')
        
        # Always create connectivity sensor
        entities.append(
            NukiConnectivitySensor(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        # Check if keypad is paired and create keypad battery binary sensor
        config = smartlock.get("config", {})
        keypad_paired = config.get("keypadPaired", False) or config.get("keypad2Paired", False)
        
        if keypad_paired and "keypadBatteryCritical" in smartlock.get("state", {}):
            entities.append(
                NukiKeypadBatteryBinarySensor(
                    api=api,
                    smartlock_id=smartlock_id,
                    smartlock_name=smartlock_name,
                    config_entry=config_entry,
                )
            )
            _LOGGER.info("Added keypad battery binary sensor for lock %s", smartlock_name)
        
        # Check if door sensor is available and create door state sensor and battery binary sensor
        state = smartlock.get("state", {})
        door_state = state.get("doorState", 0)
        
        # Only create door sensor entities if door sensor is available (doorState != 0)
        if door_state != 0:
            # Door state sensor
            entities.append(
                NukiDoorStateSensor(
                    api=api,
                    smartlock_id=smartlock_id,
                    smartlock_name=smartlock_name,
                    config_entry=config_entry,
                )
            )
            
            # Door sensor battery binary sensor
            if "doorsensorBatteryCritical" in state:
                entities.append(
                    NukiDoorSensorBatteryBinarySensor(
                        api=api,
                        smartlock_id=smartlock_id,
                        smartlock_name=smartlock_name,
                        config_entry=config_entry,
                    )
                )
                _LOGGER.info("Added door sensor battery binary sensor for lock %s (doorState: %d)", 
                           smartlock_name, door_state)
            
            _LOGGER.info("Added door state sensor for lock %s (doorState: %d)", 
                       smartlock_name, door_state)
        else:
            _LOGGER.debug("No door sensor available for lock %s (doorState: 0 - unavailable)", 
                         smartlock_name)
        
        # Add new binary sensors
        entities.append(
            NukiAutoLockBinarySensor(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        entities.append(
            NukiBatteryChargingBinarySensor(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        entities.append(
            NukiNightModeBinarySensor(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        entities.append(
            NukiWiFiEnabledBinarySensor(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        entities.append(
            NukiAutoUnlatchBinarySensor(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
    
    if entities:
        async_add_entities(entities, True)
        _LOGGER.info("Successfully set up %d Nuki binary sensor(s)", len(entities))


class NukiBinaryBaseSensor(BinarySensorEntity):
    """Base class for Nuki binary sensors."""
    
    def __init__(
        self,
        api,
        smartlock_id: int,
        smartlock_name: str,
        config_entry: ConfigEntry,
        sensor_type: str,
    ):
        """Initialize the binary sensor."""
        self._api = api
        self._smartlock_id = smartlock_id
        self._smartlock_name = smartlock_name
        self._config_entry = config_entry
        self._sensor_type = sensor_type
        
        # State tracking
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
        attrs = {
            "smartlock_id": self._smartlock_id,
            "sensor_type": self._sensor_type,
            "last_update": self._last_update,
        }
        return attrs
    
    @property 
    def _enhanced_logging(self) -> bool:
        """Check if enhanced logging is enabled."""
        return self._config_entry.options.get("enable_enhanced_logging", False)

    async def async_update(self) -> None:
        """Update the sensor state."""
        try:
            # Get full smartlock data including config
            data = await self._api.get_smartlock_full_data(self._smartlock_id)
            self._update_from_smartlock_data(data)
            
            self._attr_available = True
            self._last_update = datetime.now().isoformat()
            
        except Exception as ex:
            _LOGGER.error("Error updating binary sensor %s: %s", self._attr_name, ex)
            self._attr_available = False
            self._attr_is_on = False
    
    def _update_from_smartlock_data(self, data: Dict) -> None:
        """Update sensor from smartlock API data - to be implemented by subclasses."""
        raise NotImplementedError


class NukiConnectivitySensor(NukiBinaryBaseSensor):
    """Connectivity sensor for Nuki Smart Lock."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the connectivity sensor."""
        super().__init__(api, smartlock_id, smartlock_name, config_entry, "connectivity")
        
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_name = f"{smartlock_name} Connection"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_connection"
    
    def _update_from_smartlock_data(self, data: Dict) -> None:
        """Update sensor from smartlock API data."""
        try:
            # If we got data, the lock is connected
            self._attr_is_on = True
            
            # Check server state for additional connectivity info
            server_state = data.get("serverState", 0)
            if server_state != 0:
                # serverState != 0 might indicate connectivity issues
                self._attr_is_on = False
                        
        except Exception as ex:
            _LOGGER.error("Error parsing connectivity data: %s", ex)
            self._attr_is_on = False
    
    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        return "mdi:wifi" if self._attr_is_on else "mdi:wifi-off"


class NukiDoorStateSensor(NukiBinaryBaseSensor):
    """Door state sensor for Nuki Smart Lock."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the door state sensor."""
        super().__init__(api, smartlock_id, smartlock_name, config_entry, "door")
        
        self._attr_device_class = BinarySensorDeviceClass.DOOR
        self._attr_name = f"{smartlock_name} Door"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_door"
        
        # Additional state tracking
        self._door_state_value = None
    
    def _update_from_smartlock_data(self, data: Dict) -> None:
        """Update sensor from smartlock API data."""
        try:
            state = data.get("state", {})
            
            if "doorState" in state:
                door_state = state["doorState"]
                self._door_state_value = door_state
                
                # Updated door state mapping based on correct values:
                # 0 = unavailable, 1 = deactivated, 2 = door closed, 3 = door opened, 
                # 4 = door state unknown, 5 = calibrating
                if door_state == 3:
                    self._attr_is_on = True  # Door opened
                elif door_state == 2:
                    self._attr_is_on = False  # Door closed
                else:
                    # For states 0,1,4,5 - treat as unknown/unavailable
                    self._attr_is_on = None
                    
                if self._enhanced_logging:
                    door_state_text = {
                        0: "unavailable",
                        1: "deactivated", 
                        2: "door closed",
                        3: "door opened",
                        4: "door state unknown",
                        5: "calibrating"
                    }.get(door_state, f"unknown({door_state})")
                    
                    _LOGGER.debug("Door state: %s (raw: %s)", door_state_text, door_state)
            else:
                self._attr_is_on = None
                        
        except Exception as ex:
            _LOGGER.error("Error parsing door state data: %s", ex)
            self._attr_is_on = None
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        attrs = super().extra_state_attributes
        if self._door_state_value is not None:
            attrs["door_state_raw"] = self._door_state_value
            attrs["door_state_text"] = {
                0: "unavailable",
                1: "deactivated", 
                2: "door closed",
                3: "door opened",
                4: "door state unknown",
                5: "calibrating"
            }.get(self._door_state_value, f"unknown({self._door_state_value})")
        return attrs
    
    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        if self._attr_is_on is True:
            return "mdi:door-open"
        elif self._attr_is_on is False:
            return "mdi:door-closed"
        else:
            return "mdi:door"


class NukiKeypadBatteryBinarySensor(NukiBinaryBaseSensor):
    """Keypad battery binary sensor for Nuki Smart Lock."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the keypad battery binary sensor."""
        super().__init__(api, smartlock_id, smartlock_name, config_entry, "keypad_battery")
        
        self._attr_device_class = BinarySensorDeviceClass.BATTERY
        self._attr_name = f"{smartlock_name} Keypad Battery"
        self._attr_unique_id = f"nuki_keypad_{smartlock_id}_battery"
    
    def _update_from_smartlock_data(self, data: Dict) -> None:
        """Update sensor from smartlock API data."""
        try:
            state = data.get("state", {})
            
            if "keypadBatteryCritical" in state:
                # Binary sensor: True = battery critical/low, False = battery OK
                self._attr_is_on = bool(state["keypadBatteryCritical"])
                
                if self._enhanced_logging:
                    _LOGGER.debug("Keypad battery critical: %s", self._attr_is_on)
            else:
                self._attr_is_on = None
                        
        except Exception as ex:
            _LOGGER.error("Error parsing keypad battery data: %s", ex)
            self._attr_is_on = None
    
    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        if self._attr_is_on is True:
            return "mdi:battery-alert"
        elif self._attr_is_on is False:
            return "mdi:battery"
        else:
            return "mdi:battery-unknown"


class NukiDoorSensorBatteryBinarySensor(NukiBinaryBaseSensor):
    """Door sensor battery binary sensor for Nuki Smart Lock."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the door sensor battery binary sensor."""
        super().__init__(api, smartlock_id, smartlock_name, config_entry, "doorsensor_battery")
        
        self._attr_device_class = BinarySensorDeviceClass.BATTERY
        self._attr_name = f"{smartlock_name} Door Sensor Battery"
        self._attr_unique_id = f"nuki_doorsensor_{smartlock_id}_battery"
    
    def _update_from_smartlock_data(self, data: Dict) -> None:
        """Update sensor from smartlock API data."""
        try:
            state = data.get("state", {})
            
            if "doorsensorBatteryCritical" in state:
                # Binary sensor: True = battery critical/low, False = battery OK
                self._attr_is_on = bool(state["doorsensorBatteryCritical"])
                
                if self._enhanced_logging:
                    _LOGGER.debug("Door sensor battery critical: %s", self._attr_is_on)
            else:
                self._attr_is_on = None
                        
        except Exception as ex:
            _LOGGER.error("Error parsing door sensor battery data: %s", ex)
            self._attr_is_on = None
    
    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        if self._attr_is_on is True:
            return "mdi:battery-alert"
        elif self._attr_is_on is False:
            return "mdi:battery"
        else:
            return "mdi:battery-unknown"


class NukiAutoLockBinarySensor(NukiBinaryBaseSensor):
    """Binary sensor showing if auto lock is enabled."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the auto lock binary sensor."""
        super().__init__(api, smartlock_id, smartlock_name, config_entry, "auto_lock")
        
        self._attr_name = f"{smartlock_name} Auto Lock"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_auto_lock"
        self._timeout = None
    
    def _update_from_smartlock_data(self, data: Dict) -> None:
        """Update sensor from smartlock API data."""
        try:
            advanced_config = data.get("advancedConfig", {})
            self._attr_is_on = bool(advanced_config.get("autoLock", False))
            self._timeout = advanced_config.get("autoLockTimeout", 0)
            
            if self._enhanced_logging:
                _LOGGER.debug("Auto lock binary update: enabled=%s, timeout=%s seconds", 
                            self._attr_is_on, self._timeout)
                        
        except Exception as ex:
            _LOGGER.error("Error parsing auto lock data: %s", ex)
            self._attr_is_on = None
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        attrs = super().extra_state_attributes
        if self._timeout is not None:
            attrs["timeout_seconds"] = self._timeout
            attrs["timeout_minutes"] = self._timeout / 60
        return attrs
    
    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        return "mdi:timer-lock" if self._attr_is_on else "mdi:timer-lock-outline"


class NukiBatteryChargingBinarySensor(NukiBinaryBaseSensor):
    """Binary sensor showing if battery is charging."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the battery charging binary sensor."""
        super().__init__(api, smartlock_id, smartlock_name, config_entry, "battery_charging")
        
        self._attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
        self._attr_name = f"{smartlock_name} Battery Charging"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_battery_charging"
    
    def _update_from_smartlock_data(self, data: Dict) -> None:
        """Update sensor from smartlock API data."""
        try:
            state = data.get("state", {})
            self._attr_is_on = bool(state.get("batteryCharging", False))
            
            if self._enhanced_logging:
                _LOGGER.debug("Battery charging binary update: %s", self._attr_is_on)
                        
        except Exception as ex:
            _LOGGER.error("Error parsing battery charging data: %s", ex)
            self._attr_is_on = None
    
    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        return "mdi:battery-charging" if self._attr_is_on else "mdi:battery"


class NukiNightModeBinarySensor(NukiBinaryBaseSensor):
    """Binary sensor showing if night mode is active."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the night mode binary sensor."""
        super().__init__(api, smartlock_id, smartlock_name, config_entry, "night_mode")
        
        self._attr_name = f"{smartlock_name} Night Mode"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_night_mode"
    
    def _update_from_smartlock_data(self, data: Dict) -> None:
        """Update sensor from smartlock API data."""
        try:
            state = data.get("state", {})
            self._attr_is_on = bool(state.get("nightMode", False))
            
            if self._enhanced_logging:
                _LOGGER.debug("Night mode binary update: %s", self._attr_is_on)
                        
        except Exception as ex:
            _LOGGER.error("Error parsing night mode data: %s", ex)
            self._attr_is_on = None
    
    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        return "mdi:weather-night" if self._attr_is_on else "mdi:weather-sunny"


class NukiWiFiEnabledBinarySensor(NukiBinaryBaseSensor):
    """Binary sensor showing if WiFi is enabled."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the WiFi enabled binary sensor."""
        super().__init__(api, smartlock_id, smartlock_name, config_entry, "wifi_enabled")
        
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_name = f"{smartlock_name} WiFi Enabled"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_wifi_enabled"
    
    def _update_from_smartlock_data(self, data: Dict) -> None:
        """Update sensor from smartlock API data."""
        try:
            config = data.get("config", {})
            self._attr_is_on = bool(config.get("wifiEnabled", False))
            
            if self._enhanced_logging:
                _LOGGER.debug("WiFi enabled binary update: %s", self._attr_is_on)
                        
        except Exception as ex:
            _LOGGER.error("Error parsing WiFi enabled data: %s", ex)
            self._attr_is_on = None
    
    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        return "mdi:wifi" if self._attr_is_on else "mdi:wifi-off"


class NukiAutoUnlatchBinarySensor(NukiBinaryBaseSensor):
    """Binary sensor showing if auto unlatch is enabled."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the auto unlatch binary sensor."""
        super().__init__(api, smartlock_id, smartlock_name, config_entry, "auto_unlatch")
        
        self._attr_name = f"{smartlock_name} Auto Unlatch"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_auto_unlatch"
        self._unlatch_duration = None
    
    def _update_from_smartlock_data(self, data: Dict) -> None:
        """Update sensor from smartlock API data."""
        try:
            config = data.get("config", {})
            self._attr_is_on = bool(config.get("autoUnlatch", False))
            
            advanced_config = data.get("advancedConfig", {})
            self._unlatch_duration = advanced_config.get("unlatchDuration", 3)
            
            if self._enhanced_logging:
                _LOGGER.debug("Auto unlatch binary update: enabled=%s, duration=%s seconds", 
                            self._attr_is_on, self._unlatch_duration)
                        
        except Exception as ex:
            _LOGGER.error("Error parsing auto unlatch data: %s", ex)
            self._attr_is_on = None
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        attrs = super().extra_state_attributes
        if self._unlatch_duration is not None:
            attrs["unlatch_duration_seconds"] = self._unlatch_duration
        return attrs
    
    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        return "mdi:door-open" if self._attr_is_on else "mdi:door-closed-lock"