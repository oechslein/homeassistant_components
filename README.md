# Sensor Proxy

Clones sensor states/attributes with custom names and device binding. Perfect replacement for repetitive template sensors/macros.

## Features

- Full state + attributes copy
- Inherits unit/device_class/state_class/icon
- Optional device binding or device reuse via entity registry
- Optional utility meters for energy sensors
- **Multi-entity compact format** for creating multiple related proxies in one config block

> **Note:** Both UI config flow and YAML configuration are supported for creating single entity proxies with optional utility meters.

## Installation

1. Via HACS → Integrations → Search "Sensor Proxy"
2. Add to `configuration.yaml`:

```yaml
sensor:
  # Single entity (simple format)
  - platform: sensor_proxy
    source_entity_id: sensor.original
    unique_id: my_copy
    name: "My Copy"
    # Optional: bind to a specific device
    device_id: "your_device_id_here"

  # Multi-entity (compact format)
  - platform: sensor_proxy
    source_base: "sensor.refoss_3"
    name_base: "copy_refoss_3"
    unique_id_base: "copy_refoss_3"  # Optional
    sensors:
      - suffix: "power"
      - suffix: "energy"
        create_utility_meters: true
      - suffix: "voltage"
        name: "Custom Voltage Name"  # Override auto-generated name
      - suffix: "energy_daily"
        source_entity_id: "sensor.refoss_3_my_daily"  # Override source entity
```

## Configuration Options

### Single Entity Format

| Option                       | Required      | Type    | Description                                                       |
| ---------------------------- | ------------- | ------- | ----------------------------------------------------------------- |
| `source_entity_id`           | Yes           | string  | Entity ID to clone from                                           |
| `name`                       | At least one* | string  | Friendly name for the proxy sensor                                |
| `unique_id`                  | At least one* | string  | Unique ID for entity registry                                     |
| `device_id`                  | No            | string  | Device ID to associate the proxy with (requires `unique_id`)      |
| `create_utility_meters`      | No            | boolean | Enable utility meter creation (default: false)                    |
| `utility_meter_types`        | No            | list    | Meter cycles to create: `daily`, `weekly`, `monthly`, `yearly`    |
| `utility_name_template`      | No            | string  | Template for utility meter names (use `{cycle}` placeholder)      |
| `utility_unique_id_template` | No            | string  | Template for utility meter unique IDs (use `{cycle}` placeholder) |

*At least one of `name` or `unique_id` must be provided (both recommended).

**Example with minimal config:**

```yaml
- platform: sensor_proxy
  source_entity_id: sensor.refoss_3_energy
  unique_id: refoss_energy_copy  # Required: at least name or unique_id
  # Without name, display name will be auto-generated from entity_id
```

### Multi-Entity Format

| Option           | Required      | Type   | Description                                   |
| ---------------- | ------------- | ------ | --------------------------------------------- |
| `source_base`    | Yes           | string | Base entity ID prefix (e.g., `sensor.device`) |
| `name_base`      | At least one* | string | Base name prefix for generated proxies        |
| `unique_id_base` | At least one* | string | Base unique ID prefix for generated proxies   |
| `device_id`      | No            | string | Device ID to associate all proxies with       |
| `sensors`        | Yes           | list   | List of sensor configurations (see below)     |

*At least one of `name_base` or `unique_id_base` must be provided (both recommended).

### Sensor Item Options (within `sensors` list)

| Option                       | Required | Type    | Description                                                       |
| ---------------------------- | -------- | ------- | ----------------------------------------------------------------- |
| `suffix`                     | Yes      | string  | Suffix appended to base (creates `{source_base}_{suffix}`)        |
| `source_entity_id`           | No       | string  | Override the auto-generated source entity ID                      |
| `name`                       | No       | string  | Override the auto-generated name                                  |
| `unique_id`                  | No       | string  | Override the auto-generated unique ID                             |
| `create_utility_meters`      | No       | boolean | Enable utility meter creation for this sensor                     |
| `utility_meter_types`        | No       | list    | Meter cycles to create: `daily`, `weekly`, `monthly`, `yearly`    |
| `utility_name_template`      | No       | string  | Template for utility meter names (use `{cycle}` placeholder)      |
| `utility_unique_id_template` | No       | string  | Template for utility meter unique IDs (use `{cycle}` placeholder) |

## Utility meters (optional, per-proxy support)

You can opt-in to automatic creation of utility meters for energy sensors. This is disabled by default, and every option can be set globally or per proxy in YAML.

**Global configuration (in `configuration.yaml`):**

```yaml
sensor_proxy:
  create_utility_meters: false
  utility_meter_types:
    - daily
    - weekly
    - monthly
    - yearly
```

**Per-proxy (YAML) options:**

```yaml
sensor:
  # Single proxy example with utility meters
  - platform: sensor_proxy
    source_entity_id: sensor.refoss_3_energy
    name: copy_refoss_3_energy
    unique_id: copy_refoss_3_energy
    create_utility_meters: true
    utility_meter_types:
      - daily
      - monthly
    utility_name_template: "copy_refoss_3_energy_{cycle}"
    utility_unique_id_template: "copy_refoss_3_energy_{cycle}"

  # Multi-entity format (saves repetition)
  - platform: sensor_proxy
    source_base: "sensor.refoss_3"
    name_base: "copy_refoss_3"
    unique_id_base: "copy_refoss_3"
    sensors:
      - suffix: "power"
      - suffix: "energy"
        create_utility_meters: true
        utility_meter_types: [daily, monthly]
      - suffix: "energy_daily"
        source_entity_id: "sensor.refoss_3_today"  # Override source

  # Example with custom utility meter templates
  - platform: sensor_proxy
    source_entity_id: sensor.solar_production
    name: "Solar Production"
    unique_id: solar_production_proxy
    create_utility_meters: true
    utility_meter_types: [daily, weekly, monthly, yearly]
    # Customize utility meter naming
    utility_name_template: "solar_production_{cycle}_total"
    utility_unique_id_template: "solar_production_{cycle}_total"
    # This creates meters like:
    # - sensor.solar_production_daily_total (unique_id: solar_production_daily_total)
    # - sensor.solar_production_weekly_total (unique_id: solar_production_weekly_total)
    # - sensor.solar_production_monthly_total (unique_id: solar_production_monthly_total)
    # - sensor.solar_production_yearly_total (unique_id: solar_production_yearly_total)
```

**Behavior notes:**

- Utility meters are only created when the source sensor qualifies as an energy accumulator: it must have `state_class: total_increasing` AND `device_class: energy`.
- Utility meters are created for the generated *proxy* sensor (not the original source), with deterministic unique IDs derived from the proxy unique ID and the cycle (e.g. `_daily`).
- The integration avoids creating duplicate meters: if a meter with the same unique ID already exists in the entity registry, creation is skipped.
- Global default is `false`; enable per-proxy or set the global flag to `true` to create meters automatically.

## Use Cases

- **Device consolidation**: Associate proxies with a logical device (e.g., group related sensors from multiple hardware devices)
- **Multi-entity shorthand**: Use `source_base` + `sensors` to avoid repetitive YAML for related entities
- **Energy monitoring**: Automatically create daily/weekly/monthly/yearly utility meters for energy sensors
