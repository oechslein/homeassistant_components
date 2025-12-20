# Changelog

## 1.0.5 - 2025-12-20

- Add `source_entity_glob` with `name_template`/`unique_id_template` and `include_patterns`/`exclude_patterns` for fine-grained matching.
- Tolerate missing source entities at startup and create proxies lazily when sources appear.
- Replace deprecated state tracker API with event-based state change listeners for reliability.
- Add UI Config Flow (`config_flow.py`) and `async_setup_entry` to support configuration via the Home Assistant UI while preserving YAML support.
- Improve handling of non-numeric source states: treat `unknown`/`unavailable` as unavailable for numeric proxy sensors.
- Add programmatic `utility_meter` creation (opt-in): global `sensor_proxy.create_utility_meters` (default: false), per-proxy `create_utility_meters` and `utility_meter_types`, and templates for names/unique_ids; meters are only created for sensors with `state_class: total_increasing` and `device_class: energy`, and creation is idempotent.

## 1.0.4 - 2025-12-20

- Add UI Config Flow (`config_flow.py`) and `async_setup_entry` to support configuration via the Home Assistant UI while preserving YAML support.
- Fix handling of non-numeric source states: treat `unknown`/`unavailable` as unavailable for numeric proxy sensors to avoid ValueError.

## 1.0.3 - 2025-12-20

- Replace deprecated state tracker API with event-based state change listeners to remove deprecation warnings and improve reliability.

## 1.0.2 - 2025-12-20

- Allow proxies to be created when source entities are missing at startup; integration now listens for source entities appearing and creates proxies lazily.

## 1.0.1 - 2025-12-20

- Add HACS metadata (.hacs.json)
- Update `manifest.json` with HA compatibility and `iot_class`
- Add CHANGELOG for releases

## 1.0.0 - previous

- Initial release
