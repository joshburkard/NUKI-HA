# NUKI Smart Lock API

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Adds an integration for the NUKI SMART Lock API to Home Assistant. This integration requires [HACS](https://hacs.xyz).

# Features

this features are already integrated:

## Smart Lock 

- get Lock Status
  - Locked, Unlocked
- Services
  - Lock, Unlock, Unlatch, Lock n Go
- Events
  - Keypad events
    - access by PinCode
    - access by FingerPrint

## Setup

Recommended to be installed via [HACS](https://github.com/hacs/integration)

1. Go to HACS -> Integrations
2. [Add this repo to your HACS custom repositories](https://hacs.xyz/docs/faq/custom_repositories)
3. Search for "NUKI Smart Lock API" and install.
4. Add the configuration as documented below.
5. Restart Home Assistant

# Configuration

## Basic Configuration
```yaml
# configuration.yaml
lock:
  - platform: nuki
    api_key: "your_nuki_api_token_here"
    name: "Front Door"  # Optional, defaults to lock name from Nuki
    scan_interval: 30   # Optional, defaults to 30 seconds
```

## Advanced Configuration with Fingerprint User Mapping

```yaml
# configuration.yaml
lock:
  - platform: nuki
    api_key: "your_nuki_api_token_here"
    name: "Front Door"
    scan_interval: 30
    
    # Configure fingerprint user mapping (optional)
    fingerprint_users:
      source_1: "Alice"      # User typically using keypad source 1
      source_2: "Bob"        # User typically using keypad source 2
      source_3: "Charlie"    # Add more sources as needed
      # source_4: "David"
      # source_5: "Eve"
    
    # Time window for detecting recent keypad actions (optional)
    fingerprint_detection_window: 120  # seconds, defaults to 120 (2 minutes)
    
    # Enable detailed logging for debugging (optional)
    enable_enhanced_logging: false     # defaults to false
```

## Configuration Options

### Required Parameters

| Parameter | Type | Description |
| --- | --- | --- |
| api_key | string | Your Nuki Web API token (get from Nuki Web) | 

### Optional Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| name | string | Lock name from API | Prefix for the lock entity name | 
| scan_interval | time | 30 seconds | How often to check for lock state updates |
| fingerprint_users | dict | {} | Map keypad sources to user names for fingerprint detection |
| fingerprint_detection_window | int | 120 | Time window in seconds to detect recent keypad actions |
| enable_enhanced_logging | bool | false | Enable detailed debug logging |

## Fingerprint User Mapping
The fingerprint_users configuration helps the integration identify which user triggered a fingerprint unlock. When someone uses their fingerprint, the Nuki API typically logs it as "Nuki Keypad" without specific user identification.

### How to Configure Fingerprint Users

1. Monitor your logs with enable_enhanced_logging: true temporarily
2. Have each family member use their fingerprint and note the source number in the logs
3. Map each source to the corresponding user:

```yaml
fingerprint_users:
  source_1: "Mom"        # Mom's fingerprint shows up as source 1
  source_2: "Dad"        # Dad's fingerprint shows up as source 2
  source_3: "Teenager"   # Teen's fingerprint shows up as source 3
```

### Alternative Detection Methods
If you don't configure fingerprint_users, the integration will still try to identify users by:

Auth ID matching: Looking for recent PIN entries with the same authentication ID
Recent activity analysis: Analyzing who recently used each keypad source
Frequency analysis: Identifying the most frequent recent user

# Event Data

The integration fires nuki_keypad_action events with this data:

```yaml
event_type: nuki_keypad_action
data:
  entity_id: lock.front_door_nuki_smart_lock
  smartlock_id: 22652258303
  action: 3                           # 1=unlock, 2=lock, 3=unlatch
  user: "Alice"                       # Detected user name
  original_user_name: "Nuki Keypad"   # Original name from Nuki API
  access_method: "fingerprint"        # "pin_code" or "fingerprint"
  timestamp: "2025-05-31T12:19:30.000Z"
  time_diff_seconds: 5.6
  trigger_type: 255
  source: 1                           # Keypad source number
  auth_id: "683ac4142b86517422ca9d87"
  state: 225
  detection_reason: "trigger_255_with_user"
  sequence_number: 1                  # For multiple rapid actions
  total_events: 1
```

# Example Automations

## Basic Welcome Home

```yaml
automation:
  - alias: "Nuki Welcome Home"
    trigger:
      - platform: event
        event_type: nuki_keypad_action
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.action in [1, 3] }}"  # unlock or unlatch
    action:
      - service: notify.notify
        data:
          title: "Welcome Home!"
          message: >
            {{ trigger.event.data.user }} unlocked the door using 
            {{ trigger.event.data.access_method }}
```

## Different Actions for PIN vs Fingerprint

```yaml
automation:
  - alias: "Nuki Access Method Response"
    trigger:
      - platform: event
        event_type: nuki_keypad_action
    action:
      - choose:
          # PIN Code Access
          - conditions:
              - condition: template
                value_template: "{{ trigger.event.data.access_method == 'pin_code' }}"
            sequence:
              - service: light.turn_on
                target:
                  entity_id: light.hallway
                data:
                  color: "blue"  # Blue for PIN
          
          # Fingerprint Access
          - conditions:
              - condition: template
                value_template: "{{ trigger.event.data.access_method == 'fingerprint' }}"
            sequence:
              - service: light.turn_on
                target:
                  entity_id: light.hallway
                data:
                  color: "green"  # Green for fingerprint
```

## User-Specific Actions

```yaml
automation:
  - alias: "Nuki User Specific Welcome"
    trigger:
      - platform: event
        event_type: nuki_keypad_action
    action:
      - choose:
          - conditions:
              - condition: template
                value_template: "{{ 'Alice' in trigger.event.data.user }}"
            sequence:
              - service: scene.turn_on
                target:
                  entity_id: scene.alice_welcome_home
          
          - conditions:
              - condition: template
                value_template: "{{ 'Bob' in trigger.event.data.user }}"
            sequence:
              - service: scene.turn_on
                target:
                  entity_id: scene.bob_welcome_home
```

# Troubleshooting

## Enable Debug Logging

Add to configuration.yaml:

```yaml
logger:
  logs:
    custom_components.nuki: debug
```

Or enable enhanced logging in the platform configuration:

```yaml
lock:
  - platform: nuki
    api_key: "your_token"
    enable_enhanced_logging: true
```

## Common Issues

1. Fingerprint users not detected correctly:
    - Enable enhanced logging and check the source numbers
    - Configure fingerprint_users mapping
    - Increase fingerprint_detection_window if needed
2. Events firing multiple times:
    - This is normal for rapid PIN+fingerprint usage
    - Use sequence_number and total_events to handle multiple events
3. API connection issues:
    - Verify your API token is correct
    - Check that your Nuki Bridge is online
    - Ensure Home Assistant can reach the internet

# Getting Your API Token

1. Visit Nuki Web
2. Log in with your Nuki account
3. Go to the "API" or "Manage API" section
4. Generate a new API token
5. Copy the token to your configuration

# Services

The integration provides these additional services:

## nuki.unlatch

Unlatch the door (open without turning handle)

```yaml
action: nuki.unlatch
target:
  entity_id: lock.front_door_nuki_smart_lock
```

## nuki.lock_n_go

Lock and Go (lock and auto-unlatch after delay)

```yaml
action: nuki.lock_n_go
target:
  entity_id: lock.front_door_nuki_smart_lock
```

## Change Log

here you will find the [Change Log](changelog.md)