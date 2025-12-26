import logging
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

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

    entities = []

    # Check which configuration format is being used
    if "source_entity_id" in config:
        # Single entity configuration (legacy format)
        source_entity_id = config["source_entity_id"]
        new_unique_id = config.get(CONF_UNIQUE_ID)
        name = config.get(CONF_NAME)
        # Pass explicit value if set, otherwise None to use global default
        create_utility_meters = config.get("create_utility_meters")
        utility_meter_types = config.get("utility_meter_types")
        entities.append(
            SensorProxySensor(
                hass,
                name,
                source_entity_id,
                new_unique_id,
                device_id,
                create_utility_meters=create_utility_meters,
                utility_meter_types=utility_meter_types,
                utility_name_template=config.get("utility_name_template"),
                utility_unique_id_template=config.get("utility_unique_id_template"),
            )
        )
    elif "source_base" in config:
        # Multi-entity configuration (new compact format)
        source_base = config["source_base"]
        name_base = config["name_base"]
        unique_id_base = config.get("unique_id_base")
        sensors_list = config["sensors"]

        for sensor_config in sensors_list:
            suffix = sensor_config["suffix"]

            # Build source_entity_id from base + suffix
            source_entity_id = f"{source_base}_{suffix}"

            # Use per-sensor name if provided, otherwise generate from name_base
            name = sensor_config.get(CONF_NAME) or f"{name_base}_{suffix}"

            # Use per-sensor unique_id if provided, otherwise generate from unique_id_base
            if CONF_UNIQUE_ID in sensor_config:
                new_unique_id = sensor_config[CONF_UNIQUE_ID]
            elif unique_id_base:
                new_unique_id = f"{unique_id_base}_{suffix}"
            else:
                new_unique_id = None

            # Pass explicit value if set in sensor config, otherwise None
            create_utility_meters = sensor_config.get("create_utility_meters")
            utility_meter_types = sensor_config.get("utility_meter_types")

            entities.append(
                SensorProxySensor(
                    hass,
                    name,
                    source_entity_id,
                    new_unique_id,
                    device_id,
                    create_utility_meters=create_utility_meters,
                    utility_meter_types=utility_meter_types,
                    utility_name_template=sensor_config.get("utility_name_template"),
                    utility_unique_id_template=sensor_config.get(
                        "utility_unique_id_template"
                    ),
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
