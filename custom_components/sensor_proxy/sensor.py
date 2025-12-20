import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
)
from homeassistant.components.sensor import (
    SensorEntity,
)
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required("source_entity_id"): cv.entity_id,
        vol.Required(CONF_UNIQUE_ID): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional("device_id"): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up proxy sensors."""
    source_entity_id = config["source_entity_id"]
    new_unique_id = config[CONF_UNIQUE_ID]
    device_id = config.get("device_id")

    # Verify source exists in states
    source_state = hass.states.get(source_entity_id)
    if source_state is None:
        _LOGGER.error("Source entity %s not found", source_entity_id)
        return

    entities = [
        SensorProxySensor(
            hass, config[CONF_NAME], source_entity_id, new_unique_id, device_id
        )
    ]
    async_add_entities(entities)


class SensorProxySensor(SensorEntity):
    def __init__(self, hass, name, source_entity_id, unique_id, device_id=None):
        self._hass = hass
        self._attr_name = name
        self._attr_unique_id = unique_id  # Uses YAML unique_id directly
        self._source_entity_id = source_entity_id
        self._device_id = device_id
        self._unsub = None
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

        # Subscribe to state changes on the source entity
        self._unsub = async_track_state_change(
            self.hass, self._source_entity_id, self._async_source_changed
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe listeners when removed."""
        if self._unsub:
            self._unsub()
            self._unsub = None

    def _copy_source_attributes(self, source_state):
        """Copy attributes and state from source state object."""
        # state
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

    def update(self):
        """Legacy update method: refresh from current state."""
        source_state = self._hass.states.get(self._source_entity_id)
        if source_state:
            self._copy_source_attributes(source_state)
