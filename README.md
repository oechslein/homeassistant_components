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
    # Legacy: single entity
    source_entity_id: sensor.original
    unique_id: my_copy
    name: "My Copy"

    # Glob: create proxies for multiple matching entities
    # `*` in templates is replaced with the object_id (part after the dot)
  - platform: sensor_proxy
    source_entity_glob: "sensor.original_*"
    name_template: "copy_*"
    unique_id_template: "copy_*"
    # Optional: restrict matched wildcard (object_id) using include/exclude patterns
    include_patterns:
      - "*_power"
      - "*_energy"
    exclude_patterns:
      - "*_energy_daily"


## Utility meters (optional, per-proxy support)

You can opt-in to automatic creation of utility meters for energy sensors. This is disabled by default. As of v1.0.6, all utility meter options can be set globally or per-proxy (YAML) entry.

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
  # Single proxy example
  - platform: sensor_proxy
    source_entity_id: sensor.refoss_3_energy
    name: copy_refoss_3_energy
    unique_id: copy_refoss_3_energy
    create_utility_meters: true
    utility_meter_types:
      - daily
      - monthly
    # Optional: only for single-entity proxies
    utility_name_template: "copy_refoss_3_energy_{cycle}"
    utility_unique_id_template: "copy_refoss_3_energy_{cycle}"

  # Glob proxy example
  - platform: sensor_proxy
    source_entity_glob: "sensor.house_energy_*"
    name_template: "proxy_*"
    unique_id_template: "proxy_*"
    include_patterns:
      - "*_energy"
    exclude_patterns:
      - "*_energy_daily"
    create_utility_meters: true
    utility_meter_types:
      - daily
      - monthly
    # Optional: only for glob proxies
    utility_name_template: "proxy_*_{cycle}"
    utility_unique_id_template: "proxy_*_{cycle}"
```

**Behavior notes:**

- Utility meters are only created when the source sensor qualifies as an energy accumulator: it must have `state_class: total_increasing` AND `device_class: energy`.
- Utility meters are created for the generated *proxy* sensor (not the original source), with deterministic unique IDs derived from the proxy unique ID and the cycle (e.g. `_daily`).
- The integration avoids creating duplicate meters: if a meter with the same unique ID already exists in the entity registry, creation is skipped.
- Global default is `false`; enable per-proxy or set the global flag to `true` to create meters automatically.
