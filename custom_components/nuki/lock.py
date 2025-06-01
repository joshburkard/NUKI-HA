"""
Nuki Smart Lock Home Assistant Integration
Supports lock control and keypad event detection
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import aiohttp
import async_timeout
import voluptuous as vol
    
from homeassistant.components.lock import LockEntity, LockState, PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_DETECTION_WINDOW,
    NUKI_API_BASE,
    NUKI_STATES,
    NUKI_ACTIONS,
    EVENT_KEYPAD_ACTION,
    EVENT_MANUAL_ACTION,
    CONF_FINGERPRINT_USERS,
    CONF_FINGERPRINT_DETECTION_WINDOW,
    CONF_ENABLE_ENHANCED_LOGGING,
)

_LOGGER = logging.getLogger(__name__)

# Keypad trigger types
KEYPAD_TRIGGERS = {
    0: "web/api",
    1: "manual",
    2: "button",
    3: "automatic",
    4: "keypad",
    255: "keypad_user"
}

# Legacy YAML platform schema (for backward compatibility)
fingerprint_schema = {}
for i in range(1, 21):  # 1 to 20
    fingerprint_schema[f"source_{i}"] = cv.string

# Create schema with voluptuous
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
    vol.Optional(CONF_FINGERPRINT_USERS, default={}): vol.Schema(fingerprint_schema),
    vol.Optional(CONF_FINGERPRINT_DETECTION_WINDOW, default=DEFAULT_DETECTION_WINDOW): cv.positive_int,
    vol.Optional(CONF_ENABLE_ENHANCED_LOGGING, default=False): cv.boolean,
})


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nuki lock from config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    api = data["api"]
    smartlocks = data["smartlocks"]
    
    # Get options from config entry
    scan_interval = timedelta(seconds=config_entry.options.get(CONF_SCAN_INTERVAL, 30))
    fingerprint_users = config_entry.options.get(CONF_FINGERPRINT_USERS, {})
    detection_window = config_entry.options.get(CONF_FINGERPRINT_DETECTION_WINDOW, DEFAULT_DETECTION_WINDOW)
    enhanced_logging = config_entry.options.get(CONF_ENABLE_ENHANCED_LOGGING, False)
    
    _LOGGER.info("Setting up %d Nuki lock(s)", len(smartlocks))
    if enhanced_logging:
        _LOGGER.info("Enhanced logging enabled")
        _LOGGER.info("Fingerprint user mapping: %s", fingerprint_users)
        _LOGGER.info("Detection window: %d seconds", detection_window)
    
    # Create lock entities
    entities = []
    for smartlock in smartlocks:
        _LOGGER.info("Setting up lock: %s (ID: %s)", 
                    smartlock.get('name', 'Unknown'), 
                    smartlock.get('smartlockId', 'Unknown'))
        
        lock = NukiLock(
            api=api, 
            smartlock_data=smartlock, 
            config_entry=config_entry,
            scan_interval=scan_interval, 
            fingerprint_users=fingerprint_users, 
            detection_window=detection_window, 
            enhanced_logging=enhanced_logging
        )
        entities.append(lock)
    
    if entities:
        async_add_entities(entities, True)
        _LOGGER.info("Successfully set up %d Nuki lock(s)", len(entities))


# Legacy YAML platform setup (for backward compatibility)
async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType = None,
) -> None:
    """Set up the Nuki lock platform (legacy YAML config)."""
    _LOGGER.warning("YAML configuration is deprecated. Please use the UI to configure Nuki integration.")
    
    api_key = config[CONF_API_KEY]
    name = config.get(CONF_NAME, "")
    scan_interval = config[CONF_SCAN_INTERVAL]
    fingerprint_users = config.get(CONF_FINGERPRINT_USERS, {})
    detection_window = config.get(CONF_FINGERPRINT_DETECTION_WINDOW, DEFAULT_DETECTION_WINDOW)
    enhanced_logging = config.get(CONF_ENABLE_ENHANCED_LOGGING, False)
    
    _LOGGER.info("Setting up Nuki integration with API key: %s...", api_key[:8] + "***")
    
    # Initialize the API client
    session = async_get_clientsession(hass)
    nuki_api = NukiAPI(session, api_key)
    
    # Test API connection first
    try:
        _LOGGER.info("Testing Nuki API connection...")
        connection_ok = await nuki_api.test_connection()
        if not connection_ok:
            _LOGGER.error("Failed to connect to Nuki API - check your API token")
            return
        _LOGGER.info("Nuki API connection successful")
    except Exception as ex:
        _LOGGER.error("API connection test failed: %s", ex)
        return
    
    # Get smartlocks from API
    try:
        _LOGGER.info("Retrieving smartlocks from Nuki API...")
        smartlocks = await nuki_api.get_smartlocks()
        if not smartlocks:
            _LOGGER.error("No Nuki smartlocks found in your account")
            return
        _LOGGER.info("Found %d Nuki smartlock(s)", len(smartlocks))
    except Exception as ex:
        _LOGGER.error("Unable to retrieve smartlocks from Nuki API: %s", ex)
        return
    
    # Create lock entities
    entities = []
    for smartlock in smartlocks:
        _LOGGER.info("Setting up lock: %s (ID: %s)", 
                    smartlock.get('name', 'Unknown'), 
                    smartlock.get('smartlockId', 'Unknown'))
        lock = NukiLock(
            api=nuki_api, 
            smartlock_data=smartlock, 
            config_entry=None,  # Legacy setup
            name=name,
            scan_interval=scan_interval, 
            fingerprint_users=fingerprint_users, 
            detection_window=detection_window, 
            enhanced_logging=enhanced_logging
        )
        entities.append(lock)
    
    if entities:
        async_add_entities(entities, True)
        _LOGGER.info("Successfully set up %d Nuki lock(s)", len(entities))
    else:
        _LOGGER.error("No valid Nuki locks could be set up")


class NukiAPI:
    """Class to communicate with Nuki API."""
    
    def __init__(self, session: aiohttp.ClientSession, api_key: str):
        """Initialize the API."""
        self._session = session
        self._api_key = api_key
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        self._base_url = NUKI_API_BASE
    
    async def _request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Make API request."""
        url = f"{self._base_url}{endpoint}"
        
        _LOGGER.debug("Making %s request to %s", method, url)
        if data:
            _LOGGER.debug("Request data: %s", data)
        
        try:
            async with async_timeout.timeout(15):
                async with self._session.request(
                    method, url, headers=self._headers, json=data
                ) as response:
                    _LOGGER.debug("API Response: %s %s", response.status, response.reason)
                    
                    if response.status == 401:
                        raise Exception("Invalid API token - check your Nuki Web API token")
                    elif response.status == 403:
                        raise Exception("API access forbidden - check token permissions")
                    elif response.status == 404:
                        raise Exception(f"API endpoint not found: {endpoint}")
                    elif response.status >= 400:
                        error_text = await response.text()
                        raise Exception(f"API error {response.status}: {error_text}")
                    
                    response.raise_for_status()
                    
                    # Handle empty responses
                    content_type = response.headers.get('content-type', '')
                    if 'application/json' in content_type:
                        result = await response.json()
                        _LOGGER.debug("API Response data: %s", result)
                        return result
                    else:
                        text_result = await response.text()
                        _LOGGER.debug("API Response text: %s", text_result)
                        return {"message": text_result}
                    
        except asyncio.TimeoutError:
            raise Exception("Timeout connecting to Nuki API")
        except aiohttp.ClientError as ex:
            raise Exception(f"Error connecting to Nuki API: {ex}")
    
    async def test_connection(self) -> bool:
        """Test API connection."""
        try:
            await self._request("GET", "/account")
            return True
        except Exception as ex:
            _LOGGER.error("API connection test failed: %s", ex)
            return False
    
    async def get_smartlocks(self) -> list:
        """Get list of smartlocks."""
        try:
            _LOGGER.debug("Getting smartlocks from API...")
            result = await self._request("GET", "/smartlock")
            
            # Handle different response formats
            if isinstance(result, list):
                return result
            elif isinstance(result, dict) and 'smartlocks' in result:
                return result['smartlocks']
            elif isinstance(result, dict):
                # Single smartlock returned as dict
                return [result]
            else:
                _LOGGER.warning("Unexpected API response format: %s", type(result))
                return []
            
        except Exception as ex:
            _LOGGER.error("Failed to get smartlocks: %s", ex)
            raise
    
    async def get_smartlock_state(self, smartlock_id: int) -> Dict:
        """Get smartlock state."""
        endpoint = f"/smartlock/{smartlock_id}"
        return await self._request("GET", endpoint)
    
    async def set_smartlock_action(self, smartlock_id: int, action: int) -> Dict:
        """Send action to smartlock."""
        endpoint = f"/smartlock/{smartlock_id}/action"
        data = {"action": action}
        return await self._request("POST", endpoint, data)
    
    async def get_smartlock_logs(self, smartlock_id: int, limit: int = 50) -> list:
        """Get smartlock activity logs."""
        endpoint = f"/smartlock/{smartlock_id}/log"
        
        try:
            # Try with query parameters
            url = f"{self._base_url}{endpoint}?limit={limit}"
            
            async with async_timeout.timeout(15):
                async with self._session.get(
                    url, headers=self._headers
                ) as response:
                    if response.status == 404:
                        _LOGGER.warning("Log endpoint not available for smartlock %s", smartlock_id)
                        return []
                    elif response.status == 403:
                        _LOGGER.warning("Access to logs forbidden for smartlock %s", smartlock_id)
                        return []
                    
                    response.raise_for_status()
                    
                    content_type = response.headers.get('content-type', '')
                    if 'application/json' in content_type:
                        result = await response.json()
                        return result if isinstance(result, list) else []
                    else:
                        return []
                    
        except Exception as ex:
            _LOGGER.error("Error getting smartlock logs: %s", ex)
            return []
    
    async def get_smartlock_auth(self, smartlock_id: int) -> list:
        """Get smartlock auth entries (including keypads)."""
        endpoint = f"/smartlock/{smartlock_id}/auth"
        
        try:
            result = await self._request("GET", endpoint)
            
            # Handle different response formats
            if isinstance(result, list):
                return result
            elif isinstance(result, dict) and 'auth' in result:
                return result['auth']
            elif isinstance(result, dict):
                # Single auth entry returned as dict
                return [result]
            else:
                _LOGGER.warning("Unexpected auth response format: %s", type(result))
                return []
                
        except Exception as ex:
            _LOGGER.warning("Error getting smartlock auth entries: %s", ex)
            return []


class NukiLock(LockEntity):
    """Representation of a Nuki Smart Lock."""
    
    def __init__(
        self, 
        api: NukiAPI, 
        smartlock_data: Dict, 
        config_entry: ConfigEntry = None,
        name: str = None,
        scan_interval: timedelta = None, 
        fingerprint_users: Dict = None, 
        detection_window: int = DEFAULT_DETECTION_WINDOW, 
        enhanced_logging: bool = False
    ):
        """Initialize the lock."""
        self._api = api
        self._smartlock_id = smartlock_data["smartlockId"]
        self._smartlock_name = smartlock_data.get('name', 'Unknown Lock')
        self._config_entry = config_entry
        
        # Name handling for both config flow and legacy YAML
        if config_entry:
            # Config flow setup
            self._name = self._smartlock_name
            self._attr_name = self._smartlock_name
        else:
            # Legacy YAML setup
            self._name = f"{name} {self._smartlock_name}" if name else self._smartlock_name
            self._attr_name = self._name
        
        self._scan_interval = scan_interval or DEFAULT_SCAN_INTERVAL
        
        # Configurable fingerprint user mapping
        self._fingerprint_users = fingerprint_users or {}
        self._detection_window = detection_window
        self._enhanced_logging = enhanced_logging
        
        # State attributes
        self._state = None
        self._available = True
        self._battery_critical = False
        self._battery_level = None
        self._last_keypad_action = None
        self._last_keypad_user = None
        self._last_update = None
        self._last_manual_action = None
        
        # Store initial data
        self._update_from_data(smartlock_data)
        
        if self._enhanced_logging:
            _LOGGER.info("Nuki lock initialized with fingerprint users: %s", self._fingerprint_users)
    
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
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"nuki_{self._smartlock_id}"
    
    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available
    
    @property
    def is_locked(self) -> bool:
        """Return True if the lock is locked."""
        return self._state == LockState.LOCKED
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        attrs = {
            "smartlock_id": self._smartlock_id,
            "battery_critical": self._battery_critical,
            "last_update": self._last_update,
        }
        
        if self._battery_level is not None:
            attrs["battery_level"] = self._battery_level
        
        if self._last_keypad_action:
            attrs["last_keypad_action"] = self._last_keypad_action
            attrs["last_keypad_user"] = self._last_keypad_user
        
        return attrs
    
    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        try:
            await self._api.set_smartlock_action(self._smartlock_id, NUKI_ACTIONS["lock"])
            _LOGGER.info("Nuki lock %s: Lock command sent", self._name)
        except Exception as ex:
            _LOGGER.error("Error locking %s: %s", self._name, ex)
    
    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        try:
            await self._api.set_smartlock_action(self._smartlock_id, NUKI_ACTIONS["unlock"])
            _LOGGER.info("Nuki lock %s: Unlock command sent", self._name)
        except Exception as ex:
            _LOGGER.error("Error unlocking %s: %s", self._name, ex)
    
    async def async_unlatch(self) -> None:
        """Unlatch the device."""
        try:
            await self._api.set_smartlock_action(self._smartlock_id, NUKI_ACTIONS["unlatch"])
            _LOGGER.info("Nuki lock %s: Unlatch command sent", self._name)
        except Exception as ex:
            _LOGGER.error("Error unlatching %s: %s", self._name, ex)
    
    async def async_lock_n_go(self) -> None:
        """Lock and go."""
        try:
            await self._api.set_smartlock_action(self._smartlock_id, NUKI_ACTIONS["lock_n_go"])
            _LOGGER.info("Nuki lock %s: Lock n Go command sent", self._name)
        except Exception as ex:
            _LOGGER.error("Error Lock n Go %s: %s", self._name, ex)
    
    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        # Set up periodic updates using the correct method name
        async_track_time_interval(self.hass, self._async_update_wrapper, self._scan_interval)
        
        # Initial update
        await self.async_update()
    
    async def _async_update_wrapper(self, now) -> None:
        """Wrapper for the update method to work with async_track_time_interval."""
        await self.async_update()
    
    async def async_update(self) -> None:
        """Update the lock state."""
        try:
            # Get current state
            data = await self._api.get_smartlock_state(self._smartlock_id)
            self._update_from_data(data)
            
            # Check for keypad actions
            await self._check_keypad_actions()
            
            # Check for manual actions
            await self._check_manual_actions()
            
            self._available = True
            self._last_update = datetime.now().isoformat()
            
        except Exception as ex:
            _LOGGER.error("Error updating %s: %s", self._name, ex)
            self._available = False
    
    def _update_from_data(self, data: Dict) -> None:
        """Update entity from API data."""
        if "state" in data:
            state_id = data["state"]["state"]
            self._state = NUKI_STATES.get(state_id, "unknown")
        
        if "state" in data and "batteryCritical" in data["state"]:
            self._battery_critical = data["state"]["batteryCritical"]
        
        # Extract battery level if available
        if "config" in data and "batteryLevel" in data["config"]:
            self._battery_level = data["config"]["batteryLevel"]
    
    async def _check_keypad_actions(self) -> None:
        """Check for recent keypad actions and trigger events."""
        try:
            if self._enhanced_logging:
                _LOGGER.debug("=== Starting keypad action check for %s ===", self._name)
            
            # Get logs from API
            logs = await self._api.get_smartlock_logs(self._smartlock_id, limit=20)
            if self._enhanced_logging:
                _LOGGER.debug("Retrieved %d log entries from API", len(logs))
            
            if not logs:
                _LOGGER.warning("No logs returned from API for smartlock %s", self._smartlock_id)
                return
            
            # Get current time in UTC for proper comparison
            current_time_utc = datetime.now(timezone.utc)
            if self._enhanced_logging:
                _LOGGER.debug("Current time (UTC): %s", current_time_utc)
                _LOGGER.debug("Last processed keypad action: %s", self._last_keypad_action)
                _LOGGER.debug("Detection window: %d seconds", self._detection_window)
            
            # Collect ALL recent keypad actions within time window
            recent_keypad_actions = []
            
            # Check each log entry
            for i, log_entry in enumerate(logs):
                try:
                    # Extract basic info
                    trigger = log_entry.get("trigger")
                    action = log_entry.get("action")
                    log_date = log_entry.get("date", "")
                    user_name = log_entry.get("name", "Unknown")
                    source = log_entry.get("source")
                    auth_id = log_entry.get("authId", "")
                    state = log_entry.get("state", 0)
                    
                    if self._enhanced_logging:
                        _LOGGER.debug("Entry %d - Trigger: %s, Action: %s, Date: %s, User: %s, Source: %s", i, trigger, action, log_date, user_name, source)
                    
                    # Detect keypad actions
                    is_keypad_action = self._is_keypad_action(trigger, user_name, source, auth_id, action)
                    
                    if is_keypad_action:
                        detection_reason = self._get_detection_reason(trigger, user_name, source, auth_id, action)
                        
                        if self._enhanced_logging:
                            _LOGGER.debug("Found keypad action: %s by %s at %s (reason: %s)", 
                                        action, user_name, log_date, detection_reason)
                        
                        # Parse timestamp and check time window
                        try:
                            log_time_utc = self._parse_timestamp(log_date)
                            time_diff = (current_time_utc - log_time_utc).total_seconds()
                            
                            if self._enhanced_logging:
                                _LOGGER.debug("Time difference: %.1f seconds (%.1f minutes)", time_diff, time_diff/60)
                            
                            # Check if within time window and not already processed
                            if (time_diff < self._detection_window and time_diff >= 0 and 
                                (self._last_keypad_action is None or log_date > self._last_keypad_action)):
                                
                                # Determine access method and user
                                access_method, actual_user = self._determine_access_method_and_user(
                                    user_name, logs, i, source, auth_id)
                                
                                recent_keypad_actions.append({
                                    'log_entry': log_entry,
                                    'log_date': log_date,
                                    'log_time_utc': log_time_utc,
                                    'time_diff': time_diff,
                                    'access_method': access_method,
                                    'actual_user': actual_user,
                                    'user_name': user_name,
                                    'detection_reason': detection_reason,
                                    'action': action,
                                    'source': source,
                                    'auth_id': auth_id,
                                    'state': state,
                                    'trigger': trigger
                                })
                                
                        except Exception as time_ex:
                            _LOGGER.error("Error parsing timestamp '%s': %s", log_date, time_ex)
                            
                except Exception as entry_ex:
                    _LOGGER.error("Error processing log entry %d: %s", i, entry_ex)
                    continue
            
            # Process and fire events for recent actions
            await self._process_recent_actions(recent_keypad_actions)
            
            if self._enhanced_logging:
                _LOGGER.debug("=== Finished keypad action check ===")
            
        except Exception as ex:
            _LOGGER.error("Error in keypad action checking for %s: %s", self._name, ex)
            if self._enhanced_logging:
                _LOGGER.exception("Full exception details:")

    def _is_keypad_action(self, trigger: int, user_name: str, source: int, auth_id: str, action: int) -> bool:
        """Determine if this log entry represents a keypad action."""
        # Based on API docs: trigger 255 = keypad, source 1 = PIN, source 2 = Fingerprint
        if trigger == 255 and source in [1, 2]:
            return True
        return False
    
    def _get_detection_reason(self, trigger: int, user_name: str, source: int, auth_id: str, action: int) -> str:
        """Get the reason why this was detected as a keypad action."""
        if trigger == 255 and user_name and user_name != "Unknown" and "Nuki Web" not in user_name:
            return "trigger_255_with_user"
        elif source in [1, 2] and user_name and user_name != "Unknown":
            return f"source_{source}_with_user"
        elif auth_id and user_name and action == 3 and trigger == 255:
            return "auth_user_unlatch_255"
        return "unknown"

    def _parse_timestamp(self, log_date: str) -> datetime:
        """Parse log timestamp to UTC datetime."""
        if log_date.endswith('Z'):
            return datetime.fromisoformat(log_date.replace("Z", "+00:00"))
        elif '+' in log_date or log_date.endswith('+00:00'):
            return datetime.fromisoformat(log_date)
        else:
            log_time_naive = datetime.fromisoformat(log_date)
            return log_time_naive.replace(tzinfo=timezone.utc)
    
    def _determine_access_method_and_user(self, user_name: str, logs: list, index: int, 
                                        source: int, auth_id: str) -> tuple:
        """Determine access method and actual user."""
        # Get the current log entry to check state
        current_entry = logs[index] if index < len(logs) else {}
        state = current_entry.get("state", 0)
        
        # Based on API docs: source 1 = PIN Code, source 2 = Fingerprint
        if source == 2:
            # Check for authentication errors first
            if state == 225:  # Error wrong fingerprint
                access_method = "fingerprint"
                actual_user = "Unknown Fingerprint (Failed)"
            elif user_name == "Nuki Keypad" and state != 0:
                # Other error states with Nuki Keypad
                access_method = "fingerprint"
                actual_user = f"Unknown Fingerprint (Error {state})"
            elif user_name and user_name not in ["Nuki Keypad", "Unknown"]:
                # Successful fingerprint with real user name
                access_method = "fingerprint"
                actual_user = user_name
            else:
                # Fallback for "Nuki Keypad" with successful state
                access_method = "fingerprint"
                actual_user = self._determine_fingerprint_user_fallback(source)
                
            if self._enhanced_logging:
                _LOGGER.info("Detected fingerprint access by %s (source: %s, state: %s)", actual_user, source, state)
                
        elif source == 1:
            # Check for authentication errors first
            if state == 224:  # Error wrong entry code
                access_method = "pin_code"
                actual_user = "Unknown PIN (Failed)"
            elif user_name == "Nuki Keypad" and state != 0:
                # Other error states with PIN
                access_method = "pin_code"
                actual_user = f"Unknown PIN (Error {state})"
            elif user_name and user_name not in ["Nuki Keypad", "Unknown"]:
                # Successful PIN with real user name
                access_method = "pin_code"
                actual_user = user_name
            else:
                access_method = "pin_code"
                actual_user = "PIN User"
                
            if self._enhanced_logging:
                _LOGGER.info("Detected PIN code access by %s (source: %s, state: %s)", actual_user, source, state)
        else:
            access_method = "unknown"
            actual_user = user_name if user_name else "Unknown User"
            if self._enhanced_logging:
                _LOGGER.info("Unknown access method: user=%s, source=%s, state=%s", actual_user, source, state)
        
        return access_method, actual_user
    
    def _determine_fingerprint_user_fallback(self, source: int) -> str:
        """Fallback method when API returns 'Nuki Keypad' instead of actual user name."""
        try:
            # Use configured source mapping
            source_key = f"source_{source}"
            if source_key in self._fingerprint_users and self._fingerprint_users[source_key]:
                return self._fingerprint_users[source_key]
            
            # Fallback
            return f"Fingerprint User (Source {source})"
            
        except Exception as ex:
            _LOGGER.error("Error in fingerprint user fallback: %s", ex)
            return "Unknown Fingerprint User"

    async def _process_recent_actions(self, recent_keypad_actions: list) -> None:
        """Process and fire events for recent keypad actions."""
        if not recent_keypad_actions:
            if self._enhanced_logging:
                _LOGGER.debug("No new keypad actions found within time window")
            return
        
        _LOGGER.info("Found %d recent keypad actions to process", len(recent_keypad_actions))
        
        # Sort by timestamp (newest first)
        recent_keypad_actions.sort(key=lambda x: x['log_time_utc'], reverse=True)
        
        for idx, action_data in enumerate(recent_keypad_actions):
            if self._enhanced_logging:
                _LOGGER.info("Processing keypad action %d/%d: %s by %s via %s (%.1fs ago)", 
                           idx + 1, len(recent_keypad_actions),
                           action_data['action'], action_data['actual_user'], 
                           action_data['access_method'], action_data['time_diff'])
            
            # Create event data
            event_data = {
                "entity_id": self.entity_id,
                "smartlock_id": self._smartlock_id,
                "action": action_data['action'],
                "user": action_data['actual_user'],
                "original_user_name": action_data['user_name'],
                "access_method": action_data['access_method'],
                "timestamp": action_data['log_date'],
                "time_diff_seconds": action_data['time_diff'],
                "trigger_type": action_data['trigger'],
                "source": action_data['source'],
                "auth_id": action_data['auth_id'],
                "state": action_data['state'],
                "detection_reason": action_data['detection_reason'],
                "sequence_number": idx + 1,
                "total_events": len(recent_keypad_actions),
                "raw_entry": action_data['log_entry']
            }
            
            _LOGGER.info("Firing nuki_keypad_action event %d/%d for %s via %s", 
                       idx + 1, len(recent_keypad_actions),
                       action_data['actual_user'], action_data['access_method'])
            
            # Fire the event
            self.hass.bus.async_fire(EVENT_KEYPAD_ACTION, event_data)
            
            # Small delay between events
            if idx < len(recent_keypad_actions) - 1:
                await asyncio.sleep(0.1)
        
        # Update tracking
        most_recent = recent_keypad_actions[0]
        self._last_keypad_action = most_recent['log_date']
        self._last_keypad_user = most_recent['actual_user']
        
        if self._enhanced_logging:
            _LOGGER.debug("Updated last processed keypad action to: %s by %s", 
                         self._last_keypad_action, self._last_keypad_user)

    def _determine_fingerprint_user(self, logs: list, current_index: int, source: int, auth_id: str) -> str:
        """
        Determine the actual user for fingerprint access using configurable mappings.
        """
        try:
            if self._enhanced_logging:
                _LOGGER.debug("Determining fingerprint user for auth_id: %s, source: %s", auth_id[-8:] if auth_id else "None", source)
            
            # Method 1: Look for a recent PIN entry by the same auth_id (MOST RELIABLE)
            auth_id_window = min(20, len(logs))  # Look at more entries for auth_id matching
            for i in range(max(0, current_index - auth_id_window), min(len(logs), current_index + 5)):
                if i == current_index:
                    continue
                    
                entry = logs[i]
                entry_auth_id = entry.get("authId", "")
                entry_name = entry.get("name", "")
                entry_source = entry.get("source", 0)
                entry_trigger = entry.get("trigger", 0)
                entry_date = entry.get("date", "")
                
                # Look for PIN entries (source 1) with same auth_id
                if (entry_auth_id and entry_auth_id == auth_id and 
                    entry_source == 1 and entry_trigger == 255 and  # PIN code entry
                    entry_name and entry_name != "Unknown" and "Nuki Web" not in entry_name):
                    
                    if self._enhanced_logging:
                        _LOGGER.debug("Found fingerprint user via auth_id match: %s (from PIN entry: %s)", entry_name, entry_date)
                    return entry_name
            
            # Method 2: Use configured source mapping
            source_key = f"source_{source}"
            if source_key in self._fingerprint_users and self._fingerprint_users[source_key]:
                configured_user = self._fingerprint_users[source_key]
                if self._enhanced_logging:
                    _LOGGER.debug("Found fingerprint user via configured mapping: %s for source %s", configured_user, source)
                return configured_user
            
            # Method 3: Dynamic source mapping based on recent activity
            source_activity = self._analyze_recent_source_activity(logs, source)
            if source_activity:
                if self._enhanced_logging:
                    _LOGGER.debug("Found fingerprint user via recent activity analysis: %s", source_activity)
                return source_activity
            
            # Method 4: Look at the most frequent recent user (fallback)
            frequent_user = self._get_most_frequent_recent_user(logs)
            if frequent_user:
                if self._enhanced_logging:
                    _LOGGER.debug("Found fingerprint user via frequency analysis: %s", frequent_user)
                return frequent_user
            
            # Fallback: Return descriptive name
            fallback_name = f"Fingerprint User (Source {source})"
            if auth_id and len(auth_id) > 8:
                fallback_name += f" [{auth_id[-8:]}]"
            
            if self._enhanced_logging:
                _LOGGER.debug("Using fallback fingerprint user: %s", fallback_name)
            return fallback_name
            
        except Exception as ex:
            _LOGGER.error("Error determining fingerprint user: %s", ex)
            return "Unknown Fingerprint User"

    def _analyze_recent_source_activity(self, logs: list, target_source: int) -> str:
        """Analyze recent activity to determine likely user for a source."""
        try:
            # Look at recent PIN entries (source 1) from keypad actions
            recent_entries = logs[:15]  # Last 15 entries
            source_users = []
            
            for entry in recent_entries:
                entry_source = entry.get("source", 0)
                entry_name = entry.get("name", "")
                entry_trigger = entry.get("trigger", 0)
                
                # Look for PIN codes (source 1) from keypad (trigger 255)
                if (entry_trigger == 255 and entry_source == 1 and  # PIN code entry
                    entry_name and entry_name != "Unknown" and "Nuki Web" not in entry_name):
                    source_users.append(entry_name)
            
            if source_users:
                # Return the most recent user for PIN codes
                return source_users[0]
                
        except Exception as ex:
            if self._enhanced_logging:
                _LOGGER.debug("Error in source activity analysis: %s", ex)
        
        return None

    def _get_most_frequent_recent_user(self, logs: list) -> str:
        """Get the most frequent recent user as a last resort."""
        try:
            recent_users = []
            recent_entries = logs[:20]  # Last 20 entries
            
            for entry in recent_entries:
                user = entry.get("name", "")
                trigger = entry.get("trigger", 0)
                source = entry.get("source", 0)
                
                # Only consider keypad PIN entries
                if (trigger == 255 and source == 1 and  # PIN code entry
                    user and user != "Unknown" and "Nuki Web" not in user):
                    recent_users.append(user)
            
            if recent_users:
                # Count frequency and return most common
                from collections import Counter
                user_counts = Counter(recent_users)
                most_frequent = user_counts.most_common(1)[0][0]
                return most_frequent
                
        except Exception as ex:
            if self._enhanced_logging:
                _LOGGER.debug("Error in frequency analysis: %s", ex)
        
        return None

    async def debug_recent_logs(self) -> None:
        """Debug method to show recent logs."""
        try:
            logs = await self._api.get_smartlock_logs(self._smartlock_id, limit=10)
            _LOGGER.info("=== RECENT LOGS DEBUG ===")
            for i, log_entry in enumerate(logs):
                trigger = log_entry.get("trigger", "unknown")
                trigger_name = KEYPAD_TRIGGERS.get(trigger, f"unknown({trigger})")
                _LOGGER.info("Log %d: %s - %s by %s at %s", 
                            i, 
                            log_entry.get("action", "unknown"),
                            trigger_name,
                            log_entry.get("name", "Unknown"),
                            log_entry.get("date", "unknown"))
            _LOGGER.info("=== END RECENT LOGS ===")
        except Exception as ex:
            _LOGGER.error("Error in debug_recent_logs: %s", ex)

    async def _check_manual_actions(self) -> None:
        """Check for manual (non-keypad) actions and fire events."""
        try:
            logs = await self._api.get_smartlock_logs(self._smartlock_id, limit=10)
            current_time_utc = datetime.now(timezone.utc)
            
            for log_entry in logs:
                trigger = log_entry.get("trigger")
                action = log_entry.get("action")
                log_date = log_entry.get("date", "")
                user_name = log_entry.get("name", "")
                
                # Detect manual operations (inside handle or external key)
                if trigger == 1:  # Manual trigger
                    try:
                        log_time_utc = self._parse_timestamp(log_date)
                        time_diff = (current_time_utc - log_time_utc).total_seconds()
                        
                        # Check if within detection window and not processed
                        if (time_diff < self._detection_window and time_diff >= 0 and 
                            (self._last_manual_action is None or log_date > self._last_manual_action)):
                            
                            # Determine if inside handle or external key based on action and context
                            manual_type = self._determine_manual_type(log_entry, logs)
                            
                            # Fire manual action event
                            event_data = {
                                "entity_id": self.entity_id,
                                "smartlock_id": self._smartlock_id,
                                "action": action,
                                "manual_type": manual_type,  # "inside_handle", "external_key", or "unknown"
                                "timestamp": log_date,
                                "time_diff_seconds": time_diff,
                                "trigger_type": trigger,
                                "user_name": user_name,
                                "raw_entry": log_entry
                            }
                            
                            _LOGGER.info("Manual action detected: %s via %s", action, manual_type)
                            self.hass.bus.async_fire(EVENT_MANUAL_ACTION, event_data)
                            
                            self._last_manual_action = log_date
                            break
                            
                    except Exception as ex:
                        _LOGGER.error("Error processing manual action: %s", ex)
                        
        except Exception as ex:
            _LOGGER.error("Error checking manual actions: %s", ex)

    def _determine_manual_type(self, log_entry: dict, all_logs: list) -> str:
        """
        Determine if manual action was from inside handle or external key.
        This is based on analysis of the action type and context.
        """
        action = log_entry.get("action")
        state = log_entry.get("state", 0)
        
        # Heuristic approach - may need refinement based on your specific lock model
        if action == 1:  # Unlock action
            # If unlock action is manual, likely external key or inside handle
            # External key typically shows as unlock without specific user
            # Inside handle might show differently based on door configuration
            if log_entry.get("name") == "":
                return "external_key"
            else:
                return "inside_handle"
        elif action == 2:  # Lock action
            # Manual lock actions are typically from inside
            return "inside_handle"
        elif action == 3:  # Unlatch action
            # Manual unlatch typically from inside handle
            return "inside_handle"
        else:
            return "unknown"