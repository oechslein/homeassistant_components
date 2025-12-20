# Sensor Proxy

**Minimal YAML sensor proxy with full attribute inheritance.**

## Features

- Copies state + attributes from source sensor
- Inherits unit/device_class/state_class/icon  
- Optional device binding
- Glob-based cloning with include/exclude filters
- Optional per-proxy utility meters (configure globally or per sensor)

> UI (HACS/config flow) currently supports the single-entity case only. Use YAML for glob templates, include/exclude filters, or automatic utility meters.
