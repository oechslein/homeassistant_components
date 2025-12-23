# Changelog

## 1.1.0 - 2025-12-23

- **Breaking Change**: Removed glob pattern functionality (`source_entity_glob`, `name_template`, `unique_id_template`, `include_patterns`, `exclude_patterns`) to significantly reduce code complexity. The integration now only supports single entity proxies with optional utility meters. If you need to create multiple proxy sensors, configure them individually in YAML. ✅
- **Removed**: All glob-related helper functions and entity tracking infrastructure ✅
- **Simplified**: Core codebase now focuses exclusively on single-entity proxy with utility meter support ✅

## 1.0.19 - 2025-12-23

- **Performance**: Major optimization - eliminated global `EVENT_STATE_CHANGED` listener that processed every entity state change in Home Assistant. Now uses targeted state change listeners only for matching entities. ✅
- **Change**: Glob patterns now require explicit domain (e.g., `sensor.original_*` instead of `*.original_*`) for performance optimization and clarity. Patterns with wildcarded domains will be rejected with a warning. ✅
- **Feature**: Proxies for glob-matched entities are now created immediately at startup based on entity registry query, rather than lazily on first state change. ✅
- **Feature**: New entities matching glob patterns are detected via entity registry event subscription instead of periodic polling, providing immediate response to newly added entities. ✅

## 1.0.18 - 2025-12-21

Fix: pass unique_id when building virtual utility meters to avoid missing required arg in UtilityMeterSensor

## 1.0.17 - 2025-12-21

- Maintenance: require Home Assistant >= 2023.8.0 and updated manifests (`manifest.json`, `.hacs.json`) accordingly to rely on `SensorStateClass.TOTAL_INCREASING`. ✅

## 1.0.16 - 2025-12-21

- Fix: handle restored registry entries that don't have an active entity by creating the proxy entity instance so it can initialize from the now-available source (prevents "Forced update failed. Entity ... not found" warnings). ✅

## 1.0.15 - 2025-12-21

- Fix: initialize restored proxies when source becomes available (request an entity update for restored proxies so they are initialized from the source) ✅
- Fix: reduced noisy DEBUG logging from glob listeners and proxy updates; log only initialization/availability transitions and errors to make logs actionable ✅

## 1.0.13 - 2025-12-21

- Change: use case-sensitive matching with `fnmatch.fnmatchcase` for glob and pattern matching to make behavior predictable across platforms.
- Fix: normalize single-string include/exclude patterns and add defensive logging for pattern matching errors.
- Test: add unit tests for `matches_patterns` and expanded test coverage for single-string includes and invalid patterns.
- Log: increased debug visibility for matching decisions and proxy initialization from state_changed events.

## 1.0.12 - 2025-12-21

- Test: add unit tests for `matches_patterns` in `glob_helpers.py`.

## 1.0.11 - 2025-12-21

- Release: publish a clean v1.0.11 replacing v1.0.10 to ensure HACS compatibility and include minor packaging/release metadata fixes.

## 1.0.10 - 2025-12-20

- Add: more verbose debug logs for proxy lifecycle and utility meter lifecycle events to assist troubleshooting (creation, removal, and cleanup).

## 1.0.9 - 2025-12-20

- Fix: ensure `VirtualUtilityMeter` clears `device_class` to avoid incompatible `state_class`/`device_class` warnings when creating utility meters for non-energy source sensors.
- Fix: utility meter naming defaults now use the resolved proxy object id to avoid duplicated prefixes for glob-created proxies (e.g., avoid `copy2_copy2_...`).
- Add debug logs for lifecycle events (proxy creation/removal, utility meter build/creation/removal, glob listener cleanup) to aid troubleshooting.

## 1.0.8 - 2025-12-20

- Fix: use the entity registry object API (`registry.async_get_entity_id(...)`) in `sensor.py` to avoid AttributeError when handling state_changed events from glob listeners.
- Maintenance: small type hinting and API cleanup across core modules.

## 1.0.7 - 2025-12-20

- Add type annotations across core modules to improve static checks and developer DX.
- Consolidate glob listener helpers into `glob_helpers.py` and remove duplicate implementations from `sensor.py`.
- Fix README markdown fences to ensure example YAML renders correctly.
- Minor refactors and cleanup: export `PLATFORM_SCHEMA` from `sensor.py`, improve utility meter creation flow, and add a mypy ignore for `config_flow` domain kwarg false-positive.

## 1.0.6 - 2025-12-20

- Add full per-proxy utility meter support: `create_utility_meters`, `utility_meter_types`, `utility_name_template`, and `utility_unique_id_template` can now be set per sensor_proxy entry in YAML.
- Update schema to accept all documented per-proxy options.
- Utility meters are now created per-proxy as soon as the proxy is added, using per-proxy or global options as appropriate.
- Documentation and metadata updated for full compliance with repository instructions.
- Fix runtime bugs: per-proxy utility meters are now added via the entity platform (no more AttributeErrors or placeholder entity IDs) and glob listeners are cleaned up when Home Assistant shuts down.

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
