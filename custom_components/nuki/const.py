"""Constants for the Nuki Smart Lock integration."""
from datetime import timedelta
from homeassistant.const import Platform
from homeassistant.components.lock import LockState

# Integration domain
DOMAIN = "nuki"

# Platforms
PLATFORMS = [Platform.LOCK, Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]

# Default values
DEFAULT_NAME = "Nuki Smart Lock"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
DEFAULT_DETECTION_WINDOW = 120

# Configuration keys
CONF_FINGERPRINT_USERS = "fingerprint_users"
CONF_FINGERPRINT_DETECTION_WINDOW = "fingerprint_detection_window"
CONF_ENABLE_ENHANCED_LOGGING = "enable_enhanced_logging"

# API Configuration
NUKI_API_BASE = "https://api.nuki.io"

# Nuki states mapping
NUKI_STATES = {
    0: "uncalibrated",
    1: LockState.LOCKED,
    2: "unlocking", 
    3: LockState.UNLOCKED,
    4: "locking",
    5: "unlatched",
    6: "unlocked (lock 'n' go)",
    7: "unlatching",
    254: "motor blocked",
    255: "undefined"
}

# Nuki lock actions
NUKI_ACTIONS = {
    "unlock": 1,
    "lock": 2,
    "unlatch": 3,
    "lock_n_go": 4,
    "lock_n_go_with_unlatch": 5
}

# Event types
EVENT_KEYPAD_ACTION = "nuki_keypad_action"
EVENT_MANUAL_ACTION = "nuki_manual_action"

# Services
SERVICE_UNLATCH = "unlatch"
SERVICE_LOCK_N_GO = "lock_n_go"

# Device types
DEVICE_TYPE_SMARTLOCK = "smartlock"