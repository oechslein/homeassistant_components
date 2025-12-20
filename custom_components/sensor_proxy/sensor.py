import logging

import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.Schema(
    {
        vol.Required("source_entity_id"): str,  # Source entity_id
        vol.Required(CONF_UNIQUE_ID): str,  # New sensor unique_id
        vol.Required(CONF_NAME): str,  # New sensor name
        vol.Optional("device_id"): str,  # Optional target device_id
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up proxy sensors."""
    entity_registry = er.async_get(hass)

    source_entity_id = config["source_entity_id"]
    new_unique_id = config[CONF_UNIQUE_ID]
    device_id = config.get("device_id")

    # Verify source exists
    source_entry = entity_registry.async_get_or_none(source_entity_id)
    if not source_entry:
        _LOGGER.error(f"Source entity {source_entity_id} not found in entity registry")
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
        self._copy_source_attributes()

    async def async_added_to_hass(self) -> None:
        """Register device binding."""
        await super().async_added_to_hass()
        if self._device_id:
            entity_registry = er.async_get(self.hass)
            entity_registry.async_get_or_create(
                self.domain,
                "sensor_proxy",
                self.unique_id,
                device_id=self._device_id,
                suggested_area_id=entity_registry.async_get(
                    self._source_entity_id
                ).area_id,
            )

    def _copy_source_attributes(self):
        """Copy all from source."""
        source_state = self._hass.states.get(self._source_entity_id)
        source_entry = er.async_get(self._hass).async_get_or_none(
            self._source_entity_id
        )

        if source_state:
            self._attr_native_value = source_state.state
            self._attr_extra_state_attributes = source_state.attributes.copy()

        if source_entry:
            self._attr_native_unit_of_measurement = source_entry.unit_of_measurement
            self._attr_device_class = source_entry.device_class
            self._attr_state_class = source_entry.state_class
            self._attr_icon = source_entry.icon

    @callback
    def update(self):
        """Update from source."""
        self._copy_source_attributes()
