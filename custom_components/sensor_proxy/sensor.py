import logging
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from .config import build_utility_options
from .const import DOMAIN as DOMAIN_CONST
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

    entities = []

    # Single entity configuration
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

    if entities:
        async_add_entities(entities)


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
