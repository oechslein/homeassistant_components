# Copilot Instructions

- Support both YAML and UI (config flow) configuration for the integration.
- Keep YAML compatibility with the original usage:
  - `platform: sensor_proxy` with `source_entity_id`, `name`, and `unique_id`.
- Add HACS compatibility: include `.hacs.json`, update `manifest.json`, add changelog and README entries.
- Do not push commits to origin until the user explicitly requests `commit` and `create a new release`.
- When making changes, always update CHANGELOG.md and any relevant JSON metadata (.hacs.json, manifest.json). Do NOT document feature changes in README.md, only in CHANGELOG.md. README.md should only show usage, not change history or feature announcements.
- Use `entity_registry.async_get_or_create` correctly for device binding.
  Replace deprecated `async_track_state_change` with `async_track_state_change_event`.
- Subscribe to state changes to keep proxies updated in real time.
- Treat `unavailable`/`unknown` source states as unavailable for the proxy (do not assign strings to numeric sensors).
