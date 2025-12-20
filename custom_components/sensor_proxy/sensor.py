import fnmatch
import logging
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID, EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .config import build_utility_options
from .const import DOMAIN as DOMAIN_CONST
from .glob_helpers import (
    build_glob_listener_key,
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

    # If glob pattern provided, expand existing states and listen for new ones.
    source_glob = config.get("source_entity_glob")
    if source_glob:
        name_template = config.get("name_template", "copy_*")
        unique_template = config.get("unique_id_template", "copy_*")
        utility_options = build_utility_options(config, domain_data)

        # Track created unique_ids to avoid duplicates
        created_unique_ids = set()

        # initial scan
        include_patterns = config.get("include_patterns") or []
        exclude_patterns = config.get("exclude_patterns") or []
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
            listener_key, {"unsubscribe": None, "refcount": 0}
        )
        old_unsub = listener_entry.get("unsubscribe")
        if old_unsub:
            old_unsub()
            if old_unsub in bus_listeners:
                bus_listeners.remove(old_unsub)
        listener_entry["unsubscribe"] = None
        listener_entry.setdefault("refcount", 0)
        glob_active_keys.add(listener_key)

        for state in hass.states.async_all():
            if not fnmatch.fnmatch(state.entity_id, source_glob):
                continue
            object_id = state.entity_id.split(".", 1)[1]
            if not matches_patterns(object_id, include_patterns, exclude_patterns):
                continue

            unique_id = render_template(unique_template, state.entity_id)
            # Skip if registry already has this unique_id
            registry = er.async_get(hass)
            existing_eid = registry.async_get_entity_id(
                domain="sensor", platform="sensor_proxy", unique_id=unique_id
            )
            if existing_eid:
                _LOGGER.debug("Skipping existing proxy for unique_id %s", unique_id)
                created_unique_ids.add(unique_id)
                continue

            name = render_template(name_template, state.entity_id)
            entities.append(
                SensorProxySensor(
                    hass,
                    name,
                    state.entity_id,
                    unique_id,
                    device_id,
                    create_utility_meters=utility_options.create,
                    utility_meter_types=list(utility_options.meter_types),
                    utility_name_template=utility_options.name_template,
                    utility_unique_id_template=utility_options.unique_id_template,
                    glob_listener_key=listener_key,
                )
            )
            created_unique_ids.add(unique_id)

        # subscribe to future state changes to create proxies lazily
        @callback
        def _on_state_changed(event):
            data = event.data
            entity_id = data.get("entity_id")
            if not entity_id:
                return
            if not fnmatch.fnmatch(entity_id, source_glob):
                return
            object_id = entity_id.split(".", 1)[1]
            if not matches_patterns(object_id, include_patterns, exclude_patterns):
                return
            # create proxy if not already created
            unique_id = render_template(unique_template, entity_id)
            if unique_id in created_unique_ids:
                return
            registry = er.async_get(hass)
            existing_eid = registry.async_get_entity_id(
                domain="sensor", platform="sensor_proxy", unique_id=unique_id
            )
            if existing_eid:
                created_unique_ids.add(unique_id)
                return
            name = render_template(name_template, entity_id)
            entities_to_add = [
                SensorProxySensor(
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
            ]
            async_add_entities(entities_to_add)
            created_unique_ids.add(unique_id)

        unsubscribe = hass.bus.async_listen(EVENT_STATE_CHANGED, _on_state_changed)
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
