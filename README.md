# Sensor Proxy

Clones sensor states/attributes with custom names and device binding. Perfect replacement for repetitive template sensors/macros.

## Features

- Full state + attributes copy
- Inherits unit/device_class/state_class/icon
- Optional device binding
- Minimal YAML config

## Installation

1. Via HACS → Integrations → Search "Sensor Proxy"
2. Add to `configuration.yaml`:

```yaml
sensor:
  - platform: sensor_proxy
    source_entity_id: sensor.original
    unique_id: my_copy
    name: "My Copy"
