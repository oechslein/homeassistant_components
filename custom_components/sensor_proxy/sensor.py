import fnmatch
import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
)
from homeassistant.components.sensor import (
    SensorEntity,
)
from homeassistant.components.utility_meter import DEFAULT_OFFSET
from homeassistant.components.utility_meter.sensor import UtilityMeterSensor
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID, EVENT_STATE_CHANGED
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_CREATE_UTILITY_METERS,
    CONF_UTILITY_METER_TYPES,
    DEFAULT_UTILITY_METER_TYPES,
)
from .const import DOMAIN as DOMAIN_CONST

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        # Either `source_entity_id` (single) or `source_entity_glob` (pattern)
        vol.Optional("source_entity_id"): cv.entity_id,
        vol.Optional("source_entity_glob"): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional("unique_id_template"): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional("name_template"): cv.string,
        vol.Optional("device_id"): cv.string,
        vol.Optional("include_patterns"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("exclude_patterns"): vol.All(cv.ensure_list, [cv.string]),
        # Utility meter options (per-proxy)
        vol.Optional(CONF_CREATE_UTILITY_METERS): cv.boolean,
        vol.Optional(CONF_UTILITY_METER_TYPES): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("utility_name_template"): cv.string,
        vol.Optional("utility_unique_id_template"): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up proxy sensors."""
    device_id = config.get("device_id")

    # Helper to build name/unique_id from templates.
    def render_template(template: str, entity_id: str) -> str:
        # '*' expands to the object_id (part after the dot)
        if not template:
            return ""
        object_id = entity_id.split(".", 1)[1]
        return template.replace("*", object_id)

    def _matches_patterns(object_id: str, include, exclude) -> bool:
        # include: list of patterns that must match (if provided)
        # exclude: list of patterns that disallow a match
        if include:
            if not any(fnmatch.fnmatch(object_id, p) for p in include):
                return False
        if exclude:
            if any(fnmatch.fnmatch(object_id, p) for p in exclude):
                return False
        return True

    entities = []

    # If single entity configured (legacy)
    source_entity_id = config.get("source_entity_id")
    if source_entity_id:
        new_unique_id = config.get(CONF_UNIQUE_ID)
        name = config.get(CONF_NAME)
        # Utility meter options (per-proxy)
        create_utility_meters = config.get(CONF_CREATE_UTILITY_METERS, False)
        utility_meter_types = config.get(CONF_UTILITY_METER_TYPES)
        utility_name_template = config.get("utility_name_template")
        utility_unique_id_template = config.get("utility_unique_id_template")
        entities.append(
            SensorProxySensor(
                hass, name, source_entity_id, new_unique_id, device_id,
                create_utility_meters=create_utility_meters,
                utility_meter_types=utility_meter_types,
                utility_name_template=utility_name_template,
                utility_unique_id_template=utility_unique_id_template,
            )
        )

    # If glob pattern provided, expand existing states and listen for new ones.
    source_glob = config.get("source_entity_glob")
    if source_glob:
        name_template = config.get("name_template", "copy_*")
        unique_template = config.get("unique_id_template", "copy_*")
        # Utility meter options (per-proxy)
        create_utility_meters = config.get(CONF_CREATE_UTILITY_METERS, False)
        utility_meter_types = config.get(CONF_UTILITY_METER_TYPES)
        utility_name_template = config.get("utility_name_template")
        utility_unique_id_template = config.get("utility_unique_id_template")

        # Track created unique_ids to avoid duplicates
        created_unique_ids = set()

        # initial scan
        include_patterns = config.get("include_patterns") or []
        exclude_patterns = config.get("exclude_patterns") or []

        for state in hass.states.async_all():
            if not fnmatch.fnmatch(state.entity_id, source_glob):
                continue
            object_id = state.entity_id.split(".", 1)[1]
            if not _matches_patterns(object_id, include_patterns, exclude_patterns):
                continue

            unique_id = render_template(unique_template, state.entity_id)
            # Skip if registry already has this unique_id
            existing_eid = er.async_get_entity_id(
                hass, "sensor", "sensor_proxy", unique_id
            )
            if existing_eid:
                _LOGGER.debug("Skipping existing proxy for unique_id %s", unique_id)
                created_unique_ids.add(unique_id)
                continue

            name = render_template(name_template, state.entity_id)
            entities.append(
                SensorProxySensor(
                    hass, name, state.entity_id, unique_id, device_id,
                    create_utility_meters=create_utility_meters,
                    utility_meter_types=utility_meter_types,
                    utility_name_template=utility_name_template,
                    utility_unique_id_template=utility_unique_id_template,
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
            if not _matches_patterns(object_id, include_patterns, exclude_patterns):
                return
            # create proxy if not already created
            unique_id = render_template(unique_template, entity_id)
            if unique_id in created_unique_ids:
                return
            existing_eid = er.async_get_entity_id(
                hass, "sensor", "sensor_proxy", unique_id
            )
            if existing_eid:
                created_unique_ids.add(unique_id)
                return
            name = render_template(name_template, entity_id)
            entities_to_add = [
                SensorProxySensor(
                    hass, name, entity_id, unique_id, device_id,
                    create_utility_meters=create_utility_meters,
                    utility_meter_types=utility_meter_types,
                    utility_name_template=utility_name_template,
                    utility_unique_id_template=utility_unique_id_template,
                )
            ]
            async_add_entities(entities_to_add)
            created_unique_ids.add(unique_id)

        hass.bus.async_listen(EVENT_STATE_CHANGED, _on_state_changed)

    if entities:
        # Optionally create utility meters for each created proxy based on global config
        create_meters_global = hass.data.get(DOMAIN_CONST, {}).get(
            CONF_CREATE_UTILITY_METERS, False
        )
        global_meter_types = hass.data.get(DOMAIN_CONST, {}).get(
            CONF_UTILITY_METER_TYPES, DEFAULT_UTILITY_METER_TYPES
        )

        to_add = list(entities)
        if create_meters_global:
            for ent in entities:
                # ent is a SensorProxySensor instance but not yet added; derive proxy entity_id
                # entity_id will be assigned by HA; generate a temporary entity_id pattern
                # Use the intended name to build meter entity ids
                proxy_entity_id = async_generate_entity_id(
                    "sensor.{}", ent._attr_name.replace(" ", "_"), hass=hass
                )
                proxy_unique = ent._attr_unique_id
                # Only create meters if source/proxy qualifies — we'll check current source state
                meters = _build_utility_meters_if_applicable(
                    hass, ent, proxy_entity_id, proxy_unique, global_meter_types
                )
                to_add.extend(meters)

        async_add_entities(to_add)


def _build_utility_meters_if_applicable(
    hass, proxy_entity, proxy_entity_id, proxy_unique, meter_types
):
    """Return list of utility meter entities for proxy if source qualifies."""
    meters = []
    # Source state lives on the original source entity
    source_state = hass.states.get(proxy_entity._source_entity_id)
    if not source_state:
        return meters

    attrs = source_state.attributes
    # Require state_class == total_increasing AND device_class == energy
    if attrs.get("state_class") != "total_increasing":
        return meters
    if attrs.get("device_class") != "energy":
        return meters

    entity_registry = er.async_get(hass)

    for meter_type in meter_types:
        # Build deterministic unique id
        unique_id = f"{proxy_unique}_{meter_type}" if proxy_unique else None
        # Check if already exists
        if unique_id:
            existing = entity_registry.async_get_entity_id(
                domain="sensor", platform="utility_meter", unique_id=unique_id
            )
            if existing and hass.states.get(existing):
                _LOGGER.debug("Utility meter exists, skipping: %s", unique_id)
                continue

        # Build entity id and name
        parent_entity_id = proxy_entity_id
        name = f"{proxy_entity.name} {meter_type}"
        entity_id = f"{proxy_entity_id}_{meter_type}"

        params = {
            "hass": hass,
            "source_entity": proxy_entity._source_entity_id,
            "name": name,
            "meter_type": meter_type,
            "meter_offset": DEFAULT_OFFSET,
            "net_consumption": False,
            "tariff": None,
            "tariff_entity": None,
            "parent_meter": parent_entity_id,
            "delta_values": False,
            "cron_pattern": None,
            "periodically_resetting": False,
            "sensor_always_available": True,
            "unique_id": unique_id,
        }

        # Filter params to UtilityMeterSensor signature is handled by VirtualUtilityMeter
        utility_meter = VirtualUtilityMeter(**params)
        utility_meter.entity_id = entity_id
        meters.append(utility_meter)

        # Bookkeeping
        hass.data.setdefault(DOMAIN_CONST, {}).setdefault("created_utility_meters", {})
        if unique_id:
            hass.data[DOMAIN_CONST]["created_utility_meters"][unique_id] = entity_id

    return meters


class VirtualUtilityMeter(UtilityMeterSensor):
    """A thin wrapper around UtilityMeterSensor to provide unique_id and name."""

    def __init__(self, **kwargs):
        # UtilityMeterSensor expects certain args; powercalc filters them by signature.
        super().__init__(**{k: v for k, v in kwargs.items() if k in {"hass", "source_entity", "name", "meter_type", "meter_offset", "net_consumption", "tariff", "tariff_entity", "parent_meter", "delta_values", "cron_pattern", "periodically_resetting", "sensor_always_available"}})  # type: ignore[arg-type]
        self._attr_unique_id = kwargs.get("unique_id")

    @property
    def unique_id(self) -> str | None:
        return self._attr_unique_id


async def async_setup_entry(hass, entry, async_add_entities):
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


class SensorProxySensor(SensorEntity):
    def __init__(
        self,
        hass,
        name,
        source_entity_id,
        unique_id,
        device_id=None,
        create_utility_meters=False,
        utility_meter_types=None,
        utility_name_template=None,
        utility_unique_id_template=None,
    ):
        self._hass = hass
        self._attr_name = name
        self._attr_unique_id = unique_id  # Uses YAML unique_id directly
        self._source_entity_id = source_entity_id
        self._device_id = device_id
        self._unsub = None
        # Per-proxy utility meter options
        self._create_utility_meters = create_utility_meters
        self._utility_meter_types = utility_meter_types
        self._utility_name_template = utility_name_template
        self._utility_unique_id_template = utility_unique_id_template
        # initialize values from current state
        source_state = hass.states.get(self._source_entity_id)
        if source_state:
            self._copy_source_attributes(source_state)

    async def async_added_to_hass(self) -> None:
        """Register device binding and state listener."""
        await super().async_added_to_hass()

        # Bind to a device if requested
        if self._device_id:
            entity_registry = er.async_get(self.hass)
            source_entry = entity_registry.async_get(self._source_entity_id)
            area_id = source_entry.area_id if source_entry else None
            entity_registry.async_get_or_create(
                "sensor",
                "sensor_proxy",
                self.unique_id,
                device_id=self._device_id,
                suggested_area_id=area_id,
            )

        # Subscribe to state change events on the source entity (new API)
        self._unsub = async_track_state_change_event(
            self.hass, self._source_entity_id, self._async_source_changed_event
        )

        # Per-proxy utility meter creation (if enabled)
        if self._create_utility_meters:
            # Use per-proxy or global types
            meter_types = self._utility_meter_types
            if not meter_types:
                meter_types = self._hass.data.get(DOMAIN_CONST, {}).get(
                    CONF_UTILITY_METER_TYPES, DEFAULT_UTILITY_METER_TYPES
                )
            # Use per-proxy or fallback templates
            name_template = self._utility_name_template or f"{self._attr_name}_{{cycle}}"
            unique_id_template = self._utility_unique_id_template or f"{self._attr_unique_id}_{{cycle}}"
            # For each meter type, create a utility meter entity if not already present
            for meter_type in meter_types:
                # Render name and unique_id
                meter_name = name_template.replace("{cycle}", meter_type)
                meter_unique_id = unique_id_template.replace("{cycle}", meter_type)
                # Check if already exists
                entity_registry = er.async_get(self._hass)
                existing = entity_registry.async_get_entity_id(
                    domain="sensor", platform="utility_meter", unique_id=meter_unique_id
                )
                if existing and self._hass.states.get(existing):
                    _LOGGER.debug("Utility meter exists, skipping: %s", meter_unique_id)
                    continue
                # Only create if source qualifies
                source_state = self._hass.states.get(self._source_entity_id)
                if not source_state:
                    continue
                attrs = source_state.attributes
                if attrs.get("state_class") != "total_increasing":
                    continue
                if attrs.get("device_class") != "energy":
                    continue
                # Build params for VirtualUtilityMeter
                params = {
                    "hass": self._hass,
                    "source_entity": self._source_entity_id,
                    "name": meter_name,
                    "meter_type": meter_type,
                    "meter_offset": DEFAULT_OFFSET,
                    "net_consumption": False,
                    "tariff": None,
                    "tariff_entity": None,
                    "parent_meter": self.entity_id,
                    "delta_values": False,
                    "cron_pattern": None,
                    "periodically_resetting": False,
                    "sensor_always_available": True,
                    "unique_id": meter_unique_id,
                }
                utility_meter = VirtualUtilityMeter(**params)
                utility_meter.entity_id = f"{self.entity_id}_{meter_type}"
                # Add to HA
                self.hass.async_create_task(self.hass.helpers.entity_platform.async_add_entities([utility_meter]))
                # Bookkeeping
                self._hass.data.setdefault(DOMAIN_CONST, {}).setdefault("created_utility_meters", {})
                self._hass.data[DOMAIN_CONST]["created_utility_meters"][meter_unique_id] = utility_meter.entity_id

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe listeners when removed."""
        if self._unsub:
            self._unsub()
            self._unsub = None

    def _copy_source_attributes(self, source_state):
        """Copy attributes and state from source state object."""
        # If the source is gone or reports unavailable/unknown, mark this
        # proxy as unavailable and don't set a non-numeric state that would
        # break sensors with numeric device/state classes.
        if source_state is None or source_state.state in ("unavailable", "unknown"):
            self._attr_native_value = None
            self._attr_extra_state_attributes = None
            self._attr_native_unit_of_measurement = None
            self._attr_device_class = None
            self._attr_state_class = None
            self._attr_icon = None
            # Mark unavailable explicitly
            self._attr_available = False
            return

        # Source has a valid state — copy it and mark available.
        self._attr_available = True
        self._attr_native_value = source_state.state
        # attributes (make a shallow copy)
        self._attr_extra_state_attributes = source_state.attributes.copy()

        # common properties live on the state attributes
        attrs = source_state.attributes
        self._attr_native_unit_of_measurement = attrs.get("unit_of_measurement")
        self._attr_device_class = attrs.get("device_class")
        self._attr_state_class = attrs.get("state_class")
        self._attr_icon = attrs.get("icon")

    @callback
    def _async_source_changed(self, entity_id, old_state, new_state):
        """Handle source state changes."""
        if new_state is None:
            # source removed, clear state
            self._attr_native_value = None
            self._attr_extra_state_attributes = None
        else:
            self._copy_source_attributes(new_state)

        # Push updated state to HA
        self.async_write_ha_state()

    @callback
    def _async_source_changed_event(self, event):
        """Wrap state_changed event to the old-style callback signature."""
        data = event.data
        entity_id = data.get("entity_id")
        old_state = data.get("old_state")
        new_state = data.get("new_state")
        self._async_source_changed(entity_id, old_state, new_state)

    def update(self):
        """Legacy update method: refresh from current state."""
        source_state = self._hass.states.get(self._source_entity_id)
        if source_state:
            self._copy_source_attributes(source_state)
