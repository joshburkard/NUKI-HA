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

# Getting Your API Token

1. Visit Nuki Web
2. Log in with your Nuki account
3. Go to the "API" or "Manage API" section
4. Generate a new API token
5. Copy the token to your configuration

# Setup

Recommended to be installed via [HACS](https://github.com/hacs/integration)

1. open your [Home Assistant](https://www.home-assistant.io/) instance
2. Go to [HACS](https://hacs.xyz)
3. click on the 3 dots top right and select `Custom Repositories`
4. type in repository `https://github.com/joshburkard/NUKI-HA`
5. select the Type `Integration` and click `ADD`
6. Search for `Nuki Smart Lock API`
7. click on the 3 dots on the `Nuki Smart Lock API` row and select `Download`
8. Restart [Home Assistant](https://www.home-assistant.io/)
9. Go to `Settings` --> `Devices & Services`
10. Click to `Add Integration`
11. Search for `Nuki Smart Lock API`
12. Enter the API key, you created in the previous step and click to `Submit`.
13. use it

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