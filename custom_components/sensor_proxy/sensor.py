import fnmatch
import logging
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .config import build_utility_options
from .const import DOMAIN as DOMAIN_CONST
from .glob_helpers import (
    build_glob_listener_key,
    extract_domain_from_glob,
    get_matching_entity_ids,
    matches_patterns,
    render_template,
    schedule_glob_listener_cleanup,
)
from .proxy_sensor import SensorProxySensor
from .schema import PLATFORM_SCHEMA  # noqa: F401 - re-exported for HA

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: Callable[[list], None],
    discovery_info: Any = None,
) -> None:
    """Set up proxy sensors."""
    device_id = config.get("device_id")
    domain_data = hass.data.setdefault(DOMAIN_CONST, {})
    bus_listeners = domain_data.setdefault("bus_listeners", [])
    glob_listener_store = domain_data.setdefault("glob_listeners", {})
    glob_active_keys = domain_data.setdefault("glob_listener_active_keys", set())
    domain_data.setdefault("glob_listener_cleanup_handle", None)

    entities = []

    # If single entity configured (legacy)
    source_entity_id = config.get("source_entity_id")
    if source_entity_id:
        new_unique_id = config.get(CONF_UNIQUE_ID)
        name = config.get(CONF_NAME)
        utility_options = build_utility_options(config, domain_data)
        entities.append(
            SensorProxySensor(
                hass,
                name,
                source_entity_id,
                new_unique_id,
                device_id,
                create_utility_meters=utility_options.create,
                utility_meter_types=list(utility_options.meter_types),
                utility_name_template=utility_options.name_template,
                utility_unique_id_template=utility_options.unique_id_template,
            )
        )

    # If glob pattern provided, create proxies for all matching entities immediately.
    source_glob = config.get("source_entity_glob")
    if source_glob:
        name_template = config.get("name_template", "copy_*")
        unique_template = config.get("unique_id_template", "copy_*")
        utility_options = build_utility_options(config, domain_data)

        # Track created unique_ids to avoid duplicates
        created_unique_ids = set()

        # Get patterns for filtering
        include_patterns = config.get("include_patterns") or []
        exclude_patterns = config.get("exclude_patterns") or []
        
        # Validate that glob pattern has explicit domain
        domain = extract_domain_from_glob(source_glob)
        if not domain:
            _LOGGER.error(
                "Glob pattern '%s' must have explicit domain (e.g., 'sensor.original_*'). "
                "Skipping glob configuration.",
                source_glob,
            )
        else:
            listener_key = build_glob_listener_key(
                source_glob,
                include_patterns,
                exclude_patterns,
                name_template,
                unique_template,
                utility_options.create,
                utility_options.meter_types,
                utility_options.name_template,
                utility_options.unique_id_template,
                device_id,
            )

            listener_entry = glob_listener_store.setdefault(
                listener_key, {"unsubscribe": None, "refcount": 0, "matching_entities": set()}
            )
            old_unsub = listener_entry.get("unsubscribe")
            if old_unsub:
                old_unsub()
                if old_unsub in bus_listeners:
                    bus_listeners.remove(old_unsub)
            listener_entry["unsubscribe"] = None
            listener_entry.setdefault("refcount", 0)
            listener_entry.setdefault("matching_entities", set())
            glob_active_keys.add(listener_key)

            # Get all matching entities from registry (not just current states)
            matching_entity_ids = get_matching_entity_ids(
                hass, source_glob, include_patterns, exclude_patterns
            )
            
            # Store matching entities in listener entry for future reference
            listener_entry["matching_entities"].update(matching_entity_ids)
            
            _LOGGER.info(
                "Creating proxies for %d matching entities (glob='%s')",
                len(matching_entity_ids),
                source_glob,
            )

            # Create proxies for all matching entities immediately
            # Note: Each SensorProxySensor sets up its own targeted state change listener
            # in async_added_to_hass() via async_track_state_change_event(), so we no longer
            # need a global listener that processes all entity state changes.
            registry = er.async_get(hass)
            for entity_id in matching_entity_ids:
                state = hass.states.get(entity_id)
                
                # Skip sources that are unavailable/unknown at startup
                if state and state.state in ("unavailable", "unknown"):
                    _LOGGER.debug(
                        "Glob skip (source not available): entity_id=%s state=%s",
                        entity_id,
                        state.state,
                    )
                    continue

                unique_id = render_template(unique_template, entity_id)
                
                # Skip if registry already has this unique_id
                existing_eid = registry.async_get_entity_id(
                    domain="sensor", platform="sensor_proxy", unique_id=unique_id
                )
                if existing_eid:
                    _LOGGER.debug("Skipping existing proxy for unique_id %s", unique_id)
                    created_unique_ids.add(unique_id)
                    continue

                name = render_template(name_template, entity_id)
                entity = SensorProxySensor(
                    hass,
                    name,
                    entity_id,
                    unique_id,
                    device_id,
                    create_utility_meters=utility_options.create,
                    utility_meter_types=list(utility_options.meter_types),
                    utility_name_template=utility_options.name_template,
                    utility_unique_id_template=utility_options.unique_id_template,
                    glob_listener_key=listener_key,
                )
                _LOGGER.debug(
                    "Scheduling creation of proxy (initial scan): source=%s name=%s unique_id=%s",
                    entity_id,
                    name,
                    unique_id,
                )
                entities.append(entity)
                created_unique_ids.add(unique_id)

            # Listen for new entities being added to the registry
            # This handles entities that are added after startup
            @callback
            def _on_entity_registry_updated(event: er.Event) -> None:
                """Handle entity registry updates for new matching entities."""
                data = event.data
                
                # Only process "create" events (new entities)
                if data.get("action") != "create":
                    return
                
                entity_id = data.get("entity_id")
                if not entity_id:
                    return
                
                # Check if this entity matches our glob pattern
                if not fnmatch.fnmatchcase(entity_id, source_glob):
                    return
                
                # Check include/exclude patterns
                object_id = entity_id.split(".", 1)[1]
                if not matches_patterns(object_id, include_patterns, exclude_patterns):
                    return
                
                unique_id = render_template(unique_template, entity_id)
                
                # Skip if already created
                if unique_id in created_unique_ids:
                    return
                
                registry = er.async_get(hass)
                existing_eid = registry.async_get_entity_id(
                    domain="sensor", platform="sensor_proxy", unique_id=unique_id
                )
                if existing_eid:
                    created_unique_ids.add(unique_id)
                    return
                
                # Create proxy even if source is not yet available
                # SensorProxySensor will handle unavailable states and update when available
                name = render_template(name_template, entity_id)
                entity = SensorProxySensor(
                    hass,
                    name,
                    entity_id,
                    unique_id,
                    device_id,
                    create_utility_meters=utility_options.create,
                    utility_meter_types=list(utility_options.meter_types),
                    utility_name_template=utility_options.name_template,
                    utility_unique_id_template=utility_options.unique_id_template,
                    glob_listener_key=listener_key,
                )
                
                _LOGGER.info(
                    "Creating proxy for newly added entity: source=%s name=%s unique_id=%s",
                    entity_id,
                    name,
                    unique_id,
                )
                
                async_add_entities([entity])
                created_unique_ids.add(unique_id)
                listener_entry["matching_entities"].add(entity_id)
            
            # Subscribe to entity registry updates via event bus
            unsubscribe = hass.bus.async_listen(
                er.EVENT_ENTITY_REGISTRY_UPDATED, _on_entity_registry_updated
            )
            listener_entry["unsubscribe"] = unsubscribe
            bus_listeners.append(unsubscribe)

    if entities:
        async_add_entities(entities)

    if glob_listener_store:
        schedule_glob_listener_cleanup(hass, domain_data)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[list], None],
) -> None:
    """Set up a sensor proxy from a config entry (UI).

    This keeps YAML and UI setup working side-by-side.
    """
    data = entry.data
    source_entity_id = data["source_entity_id"]
    name = data["name"]
    unique_id = data.get(CONF_UNIQUE_ID, entry.entry_id)
    device_id = data.get("device_id")

    entities = [SensorProxySensor(hass, name, source_entity_id, unique_id, device_id)]
    async_add_entities(entities)
