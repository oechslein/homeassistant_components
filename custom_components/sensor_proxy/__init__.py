DOMAIN = "sensor_proxy"


async def async_setup(hass, config):
    """Set up the integration from YAML (no-op here)."""
    # Read global configuration under `sensor_proxy:` and store defaults
    from .const import (
        CONF_CREATE_UTILITY_METERS,
        CONF_UTILITY_METER_TYPES,
        DEFAULT_CREATE_UTILITY_METERS,
        DEFAULT_UTILITY_METER_TYPES,
    )

    conf = config.get(DOMAIN, {}) if config else {}
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][CONF_CREATE_UTILITY_METERS] = conf.get(
        CONF_CREATE_UTILITY_METERS, DEFAULT_CREATE_UTILITY_METERS
    )
    hass.data[DOMAIN][CONF_UTILITY_METER_TYPES] = conf.get(
        CONF_UTILITY_METER_TYPES, DEFAULT_UTILITY_METER_TYPES
    )

    # Keep track of created utility meters for cleanup/bookkeeping
    hass.data[DOMAIN].setdefault("created_utility_meters", {})

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry created via the UI."""
    # Forward the config entry to the sensor platform
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")
