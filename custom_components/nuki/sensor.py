"""
Nuki Smart Lock Sensor Platform
Provides battery sensors for Smart Locks, Keypads, and Door Sensors
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
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
    """Set up Nuki sensors from config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    api = data["api"]
    smartlocks = data["smartlocks"]
    
    entities = []
    
    # Create sensors for each smartlock
    for smartlock in smartlocks:
        smartlock_id = smartlock["smartlockId"]
        smartlock_name = smartlock.get('name', 'Unknown Lock')
        
        # Always create Smart Lock battery sensor
        entities.append(
            NukiSmartLockBatterySensor(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        # Create last access sensors
        entities.append(
            NukiLastAccessTimeSensor(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        entities.append(
            NukiLastAccessUserSensor(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        entities.append(
            NukiLastAccessMethodSensor(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        # Add new configuration sensors
        entities.append(
            NukiAutoLockTimeoutSensor(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        entities.append(
            NukiFirmwareVersionSensor(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        entities.append(
            NukiLEDBrightnessSensor(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        entities.append(
            NukiLockModeSensor(
                api=api,
                smartlock_id=smartlock_id,
                smartlock_name=smartlock_name,
                config_entry=config_entry,
            )
        )
        
        # Check if keypad is paired - we'll create a binary sensor instead of percentage sensor
        config = smartlock.get("config", {})
        keypad_paired = config.get("keypadPaired", False) or config.get("keypad2Paired", False)
        
        if keypad_paired and "keypadBatteryCritical" in smartlock.get("state", {}):
            _LOGGER.info("Keypad paired for lock %s - binary battery sensor will be created in binary_sensor platform", smartlock_name)
        
        # Door sensor battery will also be handled as binary sensor in binary_sensor platform
        state = smartlock.get("state", {})
        door_state = state.get("doorState", 0)
        
        if door_state != 0 and "doorsensorBatteryCritical" in state:
            _LOGGER.info("Door sensor available for lock %s - binary battery sensor will be created in binary_sensor platform", smartlock_name)
    
    if entities:
        async_add_entities(entities, True)
        _LOGGER.info("Successfully set up %d Nuki sensor(s)", len(entities))


class NukiBaseBatterySensor(SensorEntity):
    """Base class for Nuki battery sensors."""
    
    def __init__(
        self,
        api,
        smartlock_id: int,
        smartlock_name: str,
        config_entry: ConfigEntry,
        sensor_type: str,
    ):
        """Initialize the battery sensor."""
        self._api = api
        self._smartlock_id = smartlock_id
        self._smartlock_name = smartlock_name
        self._config_entry = config_entry
        self._sensor_type = sensor_type
        
        # Sensor attributes
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_suggested_display_precision = 0
        
        # State tracking
        self._attr_native_value = None
        self._attr_available = True
        self._battery_critical = False
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
            "battery_critical": self._battery_critical,
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
            # Get smartlock data
            data = await self._api.get_smartlock_full_data(self._smartlock_id)
            self._update_from_smartlock_data(data)
            
            self._attr_available = True
            self._last_update = datetime.now().isoformat()
            
            if self._enhanced_logging:
                _LOGGER.debug("%s battery update: %s%% (critical: %s)", 
                            self._attr_name, self._attr_native_value, self._battery_critical)
            
        except Exception as ex:
            _LOGGER.error("Error updating battery sensor %s: %s", self._attr_name, ex)
            self._attr_available = False
    
    def _update_from_smartlock_data(self, data: Dict) -> None:
        """Update sensor from smartlock API data - to be implemented by subclasses."""
        raise NotImplementedError
    
    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        if self._battery_critical:
            return "mdi:battery-alert"
        elif self._attr_native_value is None:
            return "mdi:battery-unknown"
        elif self._attr_native_value <= 10:
            return "mdi:battery-10"
        elif self._attr_native_value <= 20:
            return "mdi:battery-20"
        elif self._attr_native_value <= 30:
            return "mdi:battery-30"
        elif self._attr_native_value <= 40:
            return "mdi:battery-40"
        elif self._attr_native_value <= 50:
            return "mdi:battery-50"
        elif self._attr_native_value <= 60:
            return "mdi:battery-60"
        elif self._attr_native_value <= 70:
            return "mdi:battery-70"
        elif self._attr_native_value <= 80:
            return "mdi:battery-80"
        elif self._attr_native_value <= 90:
            return "mdi:battery-90"
        else:
            return "mdi:battery"


class NukiSmartLockBatterySensor(NukiBaseBatterySensor):
    """Battery sensor for Nuki Smart Lock."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the smart lock battery sensor."""
        super().__init__(api, smartlock_id, smartlock_name, config_entry, "smartlock")
        
        self._attr_name = f"{smartlock_name} Battery"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_battery"
    
    def _update_from_smartlock_data(self, data: Dict) -> None:
        """Update sensor from smartlock API data."""
        try:
            if self._enhanced_logging:
                _LOGGER.debug("Raw smartlock data for battery: %s", data.get("state", {}))
            
            state = data.get("state", {})
            
            # Method 1: batteryCharge (from your API example)
            if "batteryCharge" in state:
                battery_level = state["batteryCharge"]
                if isinstance(battery_level, (int, float)) and 0 <= battery_level <= 100:
                    self._attr_native_value = int(battery_level)
                    if self._enhanced_logging:
                        _LOGGER.debug("Found smartlock battery charge: %d%%", self._attr_native_value)
            
            # Method 2: batteryLevel (alternative)
            elif "batteryLevel" in state:
                battery_level = state["batteryLevel"]
                if isinstance(battery_level, (int, float)) and 0 <= battery_level <= 100:
                    self._attr_native_value = int(battery_level)
                    if self._enhanced_logging:
                        _LOGGER.debug("Found smartlock battery level: %d%%", self._attr_native_value)
            
            # Method 3: Check config section as fallback
            elif "config" in data and "batteryLevel" in data["config"]:
                battery_level = data["config"]["batteryLevel"]
                if isinstance(battery_level, (int, float)) and 0 <= battery_level <= 100:
                    self._attr_native_value = int(battery_level)
                    if self._enhanced_logging:
                        _LOGGER.debug("Found smartlock battery in config: %d%%", self._attr_native_value)
            
            # Check for battery critical status
            if "batteryCritical" in state:
                self._battery_critical = bool(state["batteryCritical"])
            
            if self._enhanced_logging and self._attr_native_value is None:
                _LOGGER.warning("Could not find smartlock battery level. Available state keys: %s", 
                              list(state.keys()))
                        
        except Exception as ex:
            _LOGGER.error("Error parsing smartlock battery data: %s", ex)


class NukiLastAccessTimeSensor(SensorEntity):
    """Sensor showing the date/time of last keypad access."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the last access time sensor."""
        self._api = api
        self._smartlock_id = smartlock_id
        self._smartlock_name = smartlock_name
        self._config_entry = config_entry
        
        # Sensor attributes
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_name = f"{smartlock_name} Last Access Time"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_last_access_time"
        
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
            "sensor_type": "last_access_time",
            "last_update": self._last_update,
        }
    
    @property 
    def _enhanced_logging(self) -> bool:
        """Check if enhanced logging is enabled."""
        return self._config_entry.options.get("enable_enhanced_logging", False)

    async def async_update(self) -> None:
        """Update the sensor state."""
        try:
            # Get recent logs to find last keypad access
            logs = await self._api.get_smartlock_logs(self._smartlock_id, limit=20)
            last_access_time = self._find_last_keypad_access_time(logs)
            
            if last_access_time:
                # Convert to datetime object for timestamp sensor
                self._attr_native_value = self._parse_timestamp(last_access_time)
            else:
                self._attr_native_value = None
            
            self._attr_available = True
            self._last_update = datetime.now().isoformat()
            
            if self._enhanced_logging and last_access_time:
                _LOGGER.debug("Last access time: %s", last_access_time)
            
        except Exception as ex:
            _LOGGER.error("Error updating last access time sensor: %s", ex)
            self._attr_available = False
    
    def _find_last_keypad_access_time(self, logs: list) -> str:
        """Find the most recent keypad access time from logs."""
        try:
            if self._enhanced_logging:
                _LOGGER.debug("Searching for last keypad access time in %d log entries", len(logs))
            
            for i, log_entry in enumerate(logs):
                # Look for keypad actions based on trigger and source
                trigger = log_entry.get("trigger")
                source = log_entry.get("source", 0)
                action = log_entry.get("action")
                date = log_entry.get("date", "")
                name = log_entry.get("name", "")
                
                if self._enhanced_logging:
                    _LOGGER.debug("Entry %d: trigger=%s, source=%s, name=%s, date=%s", 
                                i, trigger, source, name, date)
                
                # Detect keypad actions: trigger 255 = keypad, source 1 or 2
                if trigger == 255 and source in [1, 2]:
                    if self._enhanced_logging:
                        _LOGGER.debug("Found keypad action at index %d: %s by %s", i, date, name)
                    return date
            
            if self._enhanced_logging:
                _LOGGER.debug("No keypad actions found in logs")
            return None
            
        except Exception as ex:
            _LOGGER.error("Error finding last keypad access time: %s", ex)
            return None
    
    def _parse_timestamp(self, log_date: str) -> datetime:
        """Parse log timestamp to datetime object."""
        try:
            if log_date.endswith('Z'):
                return datetime.fromisoformat(log_date.replace("Z", "+00:00"))
            elif '+' in log_date or log_date.endswith('+00:00'):
                return datetime.fromisoformat(log_date)
            else:
                log_time_naive = datetime.fromisoformat(log_date)
                return log_time_naive.replace(tzinfo=timezone.utc)
        except Exception as ex:
            _LOGGER.error("Error parsing timestamp '%s': %s", log_date, ex)
            return None
    
    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        return "mdi:clock-outline"


class NukiLastAccessUserSensor(SensorEntity):
    """Sensor showing the user of last keypad access."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the last access user sensor."""
        self._api = api
        self._smartlock_id = smartlock_id
        self._smartlock_name = smartlock_name
        self._config_entry = config_entry
        
        # Sensor attributes
        self._attr_name = f"{smartlock_name} Last Access User"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_last_access_user"
        
        # State tracking
        self._attr_native_value = None
        self._attr_available = True
        self._last_update = None
        self._access_method = None
    
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
            "sensor_type": "last_access_user",
            "last_update": self._last_update,
        }
        if self._access_method:
            attrs["access_method"] = self._access_method
        if hasattr(self, '_access_state') and self._access_state is not None:
            attrs["access_state"] = self._access_state
            attrs["access_state_text"] = self._get_state_description(self._access_state)
        return attrs
    
    @property 
    def _enhanced_logging(self) -> bool:
        """Check if enhanced logging is enabled."""
        return self._config_entry.options.get("enable_enhanced_logging", False)

    async def async_update(self) -> None:
        """Update the sensor state."""
        try:
            # Get recent logs to find last keypad access
            logs = await self._api.get_smartlock_logs(self._smartlock_id, limit=20)
            user_info = self._find_last_keypad_access_user(logs)
            
            if user_info:
                self._attr_native_value = user_info["user"]
                self._access_method = user_info["method"]
                self._access_state = user_info.get("state", 0)
            else:
                self._attr_native_value = "Unknown"
                self._access_method = None
                self._access_state = None
            
            self._attr_available = True
            self._last_update = datetime.now().isoformat()
            
            if self._enhanced_logging and user_info:
                _LOGGER.debug("Last access user: %s via %s", user_info["user"], user_info["method"])
            
        except Exception as ex:
            _LOGGER.error("Error updating last access user sensor: %s", ex)
            self._attr_available = False
    
    def _find_last_keypad_access_user(self, logs: list) -> dict:
        """Find the most recent keypad access user from logs."""
        try:
            if self._enhanced_logging:
                _LOGGER.debug("Searching for last keypad access user in %d log entries", len(logs))
            
            # Get fingerprint users mapping from config
            fingerprint_users = self._config_entry.options.get("fingerprint_users", {})
            
            for i, log_entry in enumerate(logs):
                # Look for keypad actions (trigger 255 = keypad)
                trigger = log_entry.get("trigger")
                user_name = log_entry.get("name", "")
                action = log_entry.get("action")
                source = log_entry.get("source", 0)
                auth_id = log_entry.get("authId", "")
                state = log_entry.get("state", 0)
                
                if self._enhanced_logging:
                    _LOGGER.debug("Entry %d: trigger=%s, source=%s, name='%s', state=%s, action=%s", 
                                i, trigger, source, user_name, state, action)
                
                # Detect keypad actions: trigger 255 = keypad, source 1 (PIN) or 2 (fingerprint)
                if trigger == 255 and source in [1, 2]:
                    if self._enhanced_logging:
                        _LOGGER.debug("Found keypad action at index %d: source=%s, name='%s', state=%s", 
                                    i, source, user_name, state)
                    
                    # Determine access method and actual user based on source
                    if source == 2:  # Fingerprint
                        access_method = "fingerprint"
                        
                        # Handle different fingerprint scenarios
                        if state == 225:  # Failed fingerprint attempt
                            actual_user = "Unknown Fingerprint (Failed)"
                        elif user_name and user_name not in ["Nuki Keypad", "Unknown", ""]:
                            # API provided actual user name - use it directly
                            actual_user = user_name
                            if self._enhanced_logging:
                                _LOGGER.debug("Using direct fingerprint user name: %s", actual_user)
                        else:
                            # API returned "Nuki Keypad" or empty - try to determine actual user
                            actual_user = self._determine_fingerprint_user_advanced(logs, i, source, auth_id, fingerprint_users)
                            if self._enhanced_logging:
                                _LOGGER.debug("Determined fingerprint user via advanced logic: %s", actual_user)
                        
                    elif source == 1:  # PIN Code
                        access_method = "pin_code"
                        
                        if state == 224:  # Failed PIN attempt
                            actual_user = "Unknown PIN (Failed)"
                        elif user_name and user_name not in ["Nuki Keypad", "Unknown", ""]:
                            actual_user = user_name
                        else:
                            actual_user = "PIN User"
                    else:
                        access_method = "unknown"
                        actual_user = user_name if user_name else "Unknown User"
                    
                    if self._enhanced_logging:
                        _LOGGER.debug("Final result: method=%s, user=%s", access_method, actual_user)
                    
                    return {
                        "user": actual_user, 
                        "method": access_method, 
                        "state": state,
                        "original_name": user_name
                    }
            
            if self._enhanced_logging:
                _LOGGER.debug("No keypad actions found in logs")
            return None
            
        except Exception as ex:
            _LOGGER.error("Error finding last keypad access user: %s", ex)
            return None
    
    def _determine_fingerprint_user_advanced(self, logs: list, current_index: int, source: int, auth_id: str, fingerprint_users: dict) -> str:
        """Advanced fingerprint user determination with multiple fallback methods."""
        try:
            if self._enhanced_logging:
                _LOGGER.debug("Advanced fingerprint user detection for auth_id: %s, source: %s", 
                            auth_id[-8:] if auth_id else "None", source)
            
            # Method 1: Look for recent successful fingerprint entries with same auth_id and real names
            auth_id_window = min(50, len(logs))  # Look at more entries
            for i in range(max(0, current_index - auth_id_window), min(len(logs), current_index + 10)):
                if i == current_index:
                    continue
                    
                entry = logs[i]
                entry_auth_id = entry.get("authId", "")
                entry_name = entry.get("name", "")
                entry_source = entry.get("source", 0)
                entry_trigger = entry.get("trigger", 0)
                entry_state = entry.get("state", 0)
                entry_date = entry.get("date", "")
                
                # Look for fingerprint entries (source 2) with same auth_id and successful state
                if (entry_auth_id and entry_auth_id == auth_id and 
                    entry_source == 2 and entry_trigger == 255 and  # Fingerprint entry
                    entry_state == 0 and  # Successful state
                    entry_name and entry_name not in ["Nuki Keypad", "Unknown", ""]):
                    
                    if self._enhanced_logging:
                        _LOGGER.debug("Found fingerprint user via auth_id match: %s (from entry: %s, state: %s)", 
                                    entry_name, entry_date, entry_state)
                    return entry_name
            
            # Method 2: Look for recent PIN entries with same auth_id (user might have used PIN recently)
            for i in range(max(0, current_index - auth_id_window), min(len(logs), current_index + 10)):
                if i == current_index:
                    continue
                    
                entry = logs[i]
                entry_auth_id = entry.get("authId", "")
                entry_name = entry.get("name", "")
                entry_source = entry.get("source", 0)
                entry_trigger = entry.get("trigger", 0)
                entry_state = entry.get("state", 0)
                entry_date = entry.get("date", "")
                
                # Look for PIN entries (source 1) with same auth_id
                if (entry_auth_id and entry_auth_id == auth_id and 
                    entry_source == 1 and entry_trigger == 255 and  # PIN code entry
                    entry_state == 0 and  # Successful state
                    entry_name and entry_name not in ["Nuki Keypad", "Unknown", ""]):
                    
                    if self._enhanced_logging:
                        _LOGGER.debug("Found fingerprint user via PIN auth_id match: %s (from PIN entry: %s)", 
                                    entry_name, entry_date)
                    return entry_name
            
            # Method 3: Use configured source mapping
            source_key = f"source_{source}"
            if source_key in fingerprint_users and fingerprint_users[source_key]:
                configured_user = fingerprint_users[source_key]
                if self._enhanced_logging:
                    _LOGGER.debug("Found fingerprint user via configured mapping: %s for source %s", 
                                configured_user, source)
                return configured_user
            
            # Method 4: Look at most frequent successful fingerprint user in recent history
            frequent_fingerprint_user = self._get_most_frequent_fingerprint_user(logs)
            if frequent_fingerprint_user:
                if self._enhanced_logging:
                    _LOGGER.debug("Found fingerprint user via frequency analysis: %s", frequent_fingerprint_user)
                return frequent_fingerprint_user
            
            # Method 5: Look at most recent successful fingerprint user (regardless of auth_id)
            recent_fingerprint_user = self._get_most_recent_fingerprint_user(logs, current_index)
            if recent_fingerprint_user:
                if self._enhanced_logging:
                    _LOGGER.debug("Found fingerprint user via recent successful fingerprint: %s", recent_fingerprint_user)
                return recent_fingerprint_user
            
            # Fallback: Return descriptive name
            fallback_name = f"Fingerprint User (Source {source})"
            if auth_id and len(auth_id) > 8:
                fallback_name += f" [{auth_id[-8:]}]"
            
            if self._enhanced_logging:
                _LOGGER.debug("Using fallback fingerprint user: %s", fallback_name)
            return fallback_name
            
        except Exception as ex:
            _LOGGER.error("Error in advanced fingerprint user determination: %s", ex)
            return "Unknown Fingerprint User"

    def _get_most_frequent_fingerprint_user(self, logs: list) -> str:
        """Get the most frequent successful fingerprint user from recent logs."""
        try:
            fingerprint_users = []
            recent_entries = logs[:30]  # Last 30 entries
            
            for entry in recent_entries:
                user = entry.get("name", "")
                trigger = entry.get("trigger", 0)
                source = entry.get("source", 0)
                state = entry.get("state", 0)
                
                # Only consider successful fingerprint entries with real names
                if (trigger == 255 and source == 2 and state == 0 and  # Successful fingerprint
                    user and user not in ["Nuki Keypad", "Unknown", ""]):
                    fingerprint_users.append(user)
            
            if fingerprint_users:
                # Count frequency and return most common
                from collections import Counter
                user_counts = Counter(fingerprint_users)
                most_frequent = user_counts.most_common(1)[0][0]
                return most_frequent
                
        except Exception as ex:
            if self._enhanced_logging:
                _LOGGER.debug("Error in fingerprint frequency analysis: %s", ex)
        
        return None

    def _get_most_recent_fingerprint_user(self, logs: list, current_index: int) -> str:
        """Get the most recent successful fingerprint user (excluding current entry)."""
        try:
            # Look backwards from current entry
            for i in range(current_index + 1, min(len(logs), current_index + 20)):
                entry = logs[i]
                user = entry.get("name", "")
                trigger = entry.get("trigger", 0)
                source = entry.get("source", 0)
                state = entry.get("state", 0)
                
                # Look for successful fingerprint entries with real names
                if (trigger == 255 and source == 2 and state == 0 and  # Successful fingerprint
                    user and user not in ["Nuki Keypad", "Unknown", ""]):
                    return user
                
        except Exception as ex:
            if self._enhanced_logging:
                _LOGGER.debug("Error finding recent fingerprint user: %s", ex)
        
        return None
    
    def _get_state_description(self, state: int) -> str:
        """Get human readable description of the state."""
        state_descriptions = {
            0: "Success",
            1: "Locked",
            2: "Unlocking", 
            3: "Unlocked",
            4: "Locking",
            5: "Unlatched",
            6: "Unlocked (Lock 'n' Go)",
            7: "Unlatching",
            224: "Error: Wrong PIN Code",
            225: "Error: Wrong Fingerprint",
            254: "Motor Blocked",
            255: "Undefined"
        }
        return state_descriptions.get(state, f"Unknown State ({state})")
    
    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        # Check if this was a failed access attempt
        if hasattr(self, '_access_state') and self._access_state in [224, 225]:
            return "mdi:account-alert"
        elif self._access_method == "fingerprint":
            return "mdi:fingerprint"
        elif self._access_method == "pin_code":
            return "mdi:numeric"
        else:
            return "mdi:account"


class NukiLastAccessMethodSensor(SensorEntity):
    """Sensor showing the method of last keypad access."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the last access method sensor."""
        self._api = api
        self._smartlock_id = smartlock_id
        self._smartlock_name = smartlock_name
        self._config_entry = config_entry
        
        # Sensor attributes
        self._attr_name = f"{smartlock_name} Last Access Method"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_last_access_method"
        
        # State tracking
        self._attr_native_value = None
        self._attr_available = True
        self._last_update = None
        self._user_name = None
    
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
            "sensor_type": "last_access_method",
            "last_update": self._last_update,
        }
        if self._user_name:
            attrs["user_name"] = self._user_name
        if hasattr(self, '_source') and self._source is not None:
            attrs["source"] = self._source
        if hasattr(self, '_method_state') and self._method_state is not None:
            attrs["state"] = self._method_state
            attrs["state_text"] = self._get_state_description(self._method_state)
        return attrs
    
    @property 
    def _enhanced_logging(self) -> bool:
        """Check if enhanced logging is enabled."""
        return self._config_entry.options.get("enable_enhanced_logging", False)

    async def async_update(self) -> None:
        """Update the sensor state."""
        try:
            # Get recent logs to find last keypad access
            logs = await self._api.get_smartlock_logs(self._smartlock_id, limit=20)
            method_info = self._find_last_keypad_access_method(logs)
            
            if method_info:
                self._attr_native_value = method_info["method"]
                self._user_name = method_info["user"]
                # Store source and state info for debugging
                if "source" in method_info:
                    self._source = method_info["source"]
                if "state" in method_info:
                    self._method_state = method_info["state"]
            else:
                self._attr_native_value = "Unknown"
                self._user_name = None
                self._source = None
                self._method_state = None
            
            self._attr_available = True
            self._last_update = datetime.now().isoformat()
            
            if self._enhanced_logging and method_info:
                _LOGGER.debug("Last access method: %s by %s", method_info["method"], method_info["user"])
            
        except Exception as ex:
            _LOGGER.error("Error updating last access method sensor: %s", ex)
            self._attr_available = False
    
    def _find_last_keypad_access_method(self, logs: list) -> dict:
        """Find the most recent keypad access method from logs."""
        try:
            if self._enhanced_logging:
                _LOGGER.debug("Searching for last keypad access method in %d log entries", len(logs))
            
            for i, log_entry in enumerate(logs):
                # Look for keypad actions based on trigger and source
                trigger = log_entry.get("trigger")
                source = log_entry.get("source", 0)
                user_name = log_entry.get("name", "")
                action = log_entry.get("action")
                state = log_entry.get("state", 0)
                date = log_entry.get("date", "")
                
                if self._enhanced_logging:
                    _LOGGER.debug("Entry %d: trigger=%s, source=%s, name=%s, state=%s, date=%s", 
                                i, trigger, source, user_name, state, date)
                
                # Detect keypad actions: trigger 255 = keypad, source 1 or 2
                if trigger == 255 and source in [1, 2]:
                    if self._enhanced_logging:
                        _LOGGER.debug("Found keypad action at index %d: %s by %s (source %s, state %s)", 
                                    i, date, user_name, source, state)
                    
                    # Determine access method based on source
                    if source == 2:
                        if state == 225:  # Error wrong fingerprint
                            access_method = "Fingerprint (Failed)"
                        else:
                            access_method = "Fingerprint"
                    elif source == 1:
                        if state == 224:  # Error wrong PIN
                            access_method = "PIN Code (Failed)"
                        else:
                            access_method = "PIN Code"
                    else:
                        access_method = "Unknown"
                    
                    # Use actual user name from API
                    actual_user = user_name if user_name and user_name != "Unknown" else "Unknown User"
                    
                    if self._enhanced_logging:
                        _LOGGER.debug("Determined method: %s, user: %s", access_method, actual_user)
                    
                    return {"method": access_method, "user": actual_user, "source": source, "state": state}
            
            if self._enhanced_logging:
                _LOGGER.debug("No keypad actions found in logs")
            return None
            
        except Exception as ex:
            _LOGGER.error("Error finding last keypad access method: %s", ex)
            return None
    
    def _get_state_description(self, state: int) -> str:
        """Get human readable description of the state."""
        state_descriptions = {
            0: "Success",
            1: "Locked",
            2: "Unlocking", 
            3: "Unlocked",
            4: "Locking",
            5: "Unlatched",
            6: "Unlocked (Lock 'n' Go)",
            7: "Unlatching",
            224: "Error: Wrong PIN Code",
            225: "Error: Wrong Fingerprint",
            254: "Motor Blocked",
            255: "Undefined"
        }
        return state_descriptions.get(state, f"Unknown State ({state})")
    
    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        # Check if this was a failed access attempt
        if hasattr(self, '_method_state') and self._method_state in [224, 225]:
            return "mdi:alert-circle"
        elif self._attr_native_value and "Fingerprint" in self._attr_native_value:
            return "mdi:fingerprint"
        elif self._attr_native_value and "PIN Code" in self._attr_native_value:
            return "mdi:numeric"
        else:
            return "mdi:help-circle"


class NukiAutoLockTimeoutSensor(SensorEntity):
    """Sensor showing auto lock timeout in seconds."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the auto lock timeout sensor."""
        self._api = api
        self._smartlock_id = smartlock_id
        self._smartlock_name = smartlock_name
        self._config_entry = config_entry
        
        self._attr_name = f"{smartlock_name} Auto Lock Timeout"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_auto_lock_timeout"
        self._attr_native_unit_of_measurement = "s"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_state_class = SensorStateClass.MEASUREMENT
        
        self._attr_native_value = None
        self._attr_available = True
        self._auto_lock_enabled = None
    
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
            "auto_lock_enabled": self._auto_lock_enabled,
            "timeout_minutes": self._attr_native_value / 60 if self._attr_native_value else None,
        }
    
    @property 
    def _enhanced_logging(self) -> bool:
        """Check if enhanced logging is enabled."""
        return self._config_entry.options.get("enable_enhanced_logging", False)

    async def async_update(self) -> None:
        """Update the sensor state."""
        try:
            data = await self._api.get_smartlock_full_data(self._smartlock_id)
            
            advanced_config = data.get("advancedConfig", {})
            self._auto_lock_enabled = advanced_config.get("autoLock", False)
            
            if self._auto_lock_enabled:
                self._attr_native_value = advanced_config.get("autoLockTimeout", 0)
            else:
                self._attr_native_value = None
                
            self._attr_available = True
            
            if self._enhanced_logging:
                _LOGGER.debug("Auto lock timeout update: enabled=%s, timeout=%s", 
                            self._auto_lock_enabled, self._attr_native_value)
            
        except Exception as ex:
            _LOGGER.error("Error updating auto lock timeout sensor: %s", ex)
            self._attr_available = False
    
    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        if self._auto_lock_enabled:
            return "mdi:timer-lock"
        else:
            return "mdi:timer-lock-outline"


class NukiFirmwareVersionSensor(SensorEntity):
    """Sensor showing firmware version."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the firmware version sensor."""
        self._api = api
        self._smartlock_id = smartlock_id
        self._smartlock_name = smartlock_name
        self._config_entry = config_entry
        
        self._attr_name = f"{smartlock_name} Firmware Version"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_firmware_version"
        
        self._attr_native_value = None
        self._attr_available = True
        self._raw_version = None
        self._hardware_version = None
    
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
            "raw_firmware_version": self._raw_version,
            "hardware_version": self._hardware_version,
        }
    
    @property 
    def _enhanced_logging(self) -> bool:
        """Check if enhanced logging is enabled."""
        return self._config_entry.options.get("enable_enhanced_logging", False)

    async def async_update(self) -> None:
        """Update the sensor state."""
        try:
            data = await self._api.get_smartlock_full_data(self._smartlock_id)
            
            self._raw_version = data.get("firmwareVersion")
            self._hardware_version = data.get("hardwareVersion")
            
            if self._raw_version:
                self._attr_native_value = self._format_firmware_version(self._raw_version)
            else:
                self._attr_native_value = "Unknown"
                
            self._attr_available = True
            
            if self._enhanced_logging:
                _LOGGER.debug("Firmware version update: raw=%s, formatted=%s", 
                            self._raw_version, self._attr_native_value)
            
        except Exception as ex:
            _LOGGER.error("Error updating firmware version sensor: %s", ex)
            self._attr_available = False
    
    def _format_firmware_version(self, raw_version: int) -> str:
        """Convert raw firmware version to readable format."""
        try:
            # Based on Nuki firmware version format
            # Example: 328455 might be version 3.2.8455 or similar
            version_str = str(raw_version)
            if len(version_str) >= 6:
                major = version_str[0]
                minor = version_str[1:3].lstrip('0') or '0'
                build = version_str[3:]
                return f"{major}.{minor}.{build}"
            else:
                return f"1.0.{raw_version}"
        except:
            return str(raw_version)
    
    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        return "mdi:chip"


class NukiLEDBrightnessSensor(SensorEntity):
    """Sensor showing LED brightness level."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the LED brightness sensor."""
        self._api = api
        self._smartlock_id = smartlock_id
        self._smartlock_name = smartlock_name
        self._config_entry = config_entry
        
        self._attr_name = f"{smartlock_name} LED Brightness"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_led_brightness"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        
        self._attr_native_value = None
        self._attr_available = True
        self._led_enabled = None
    
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
            "led_enabled": self._led_enabled,
            "brightness_percentage": (self._attr_native_value * 20) if self._attr_native_value else None,
        }
    
    @property 
    def _enhanced_logging(self) -> bool:
        """Check if enhanced logging is enabled."""
        return self._config_entry.options.get("enable_enhanced_logging", False)

    async def async_update(self) -> None:
        """Update the sensor state."""
        try:
            data = await self._api.get_smartlock_full_data(self._smartlock_id)
            
            config = data.get("config", {})
            self._led_enabled = config.get("ledEnabled", False)
            
            if self._led_enabled:
                self._attr_native_value = config.get("ledBrightness", 3)
            else:
                self._attr_native_value = 0
                
            self._attr_available = True
            
            if self._enhanced_logging:
                _LOGGER.debug("LED brightness update: enabled=%s, brightness=%s", 
                            self._led_enabled, self._attr_native_value)
            
        except Exception as ex:
            _LOGGER.error("Error updating LED brightness sensor: %s", ex)
            self._attr_available = False
    
    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        if self._led_enabled and self._attr_native_value and self._attr_native_value > 0:
            if self._attr_native_value <= 1:
                return "mdi:led-strip-variant"
            elif self._attr_native_value <= 3:
                return "mdi:led-strip"
            else:
                return "mdi:led-strip-variant"
        else:
            return "mdi:led-off"


class NukiLockModeSensor(SensorEntity):
    """Sensor showing current lock mode."""
    
    def __init__(self, api, smartlock_id: int, smartlock_name: str, config_entry: ConfigEntry):
        """Initialize the lock mode sensor."""
        self._api = api
        self._smartlock_id = smartlock_id
        self._smartlock_name = smartlock_name
        self._config_entry = config_entry
        
        self._attr_name = f"{smartlock_name} Lock Mode"
        self._attr_unique_id = f"nuki_smartlock_{smartlock_id}_lock_mode"
        
        self._attr_native_value = None
        self._attr_available = True
        self._raw_mode = None
    
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
            "raw_mode": self._raw_mode,
        }
    
    @property 
    def _enhanced_logging(self) -> bool:
        """Check if enhanced logging is enabled."""
        return self._config_entry.options.get("enable_enhanced_logging", False)

    async def async_update(self) -> None:
        """Update the sensor state."""
        try:
            data = await self._api.get_smartlock_full_data(self._smartlock_id)
            
            state = data.get("state", {})
            self._raw_mode = state.get("mode", 0)
            
            # Map mode values to readable strings
            mode_mapping = {
                0: "Maintenance",
                1: "Door Mode", 
                2: "Continuous Mode",
                3: "Always Locked",
            }
            
            self._attr_native_value = mode_mapping.get(self._raw_mode, f"Unknown ({self._raw_mode})")
            self._attr_available = True
            
            if self._enhanced_logging:
                _LOGGER.debug("Lock mode update: raw=%s, mapped=%s", 
                            self._raw_mode, self._attr_native_value)
            
        except Exception as ex:
            _LOGGER.error("Error updating lock mode sensor: %s", ex)
            self._attr_available = False
    
    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        if self._raw_mode == 0:
            return "mdi:wrench"
        elif self._raw_mode == 1:
            return "mdi:door"
        elif self._raw_mode == 2:
            return "mdi:refresh"
        elif self._raw_mode == 3:
            return "mdi:lock"
        else:
            return "mdi:help-circle"