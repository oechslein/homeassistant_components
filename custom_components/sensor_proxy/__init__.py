DOMAIN = "sensor_proxy"


async def async_setup(hass, config):
    """Set up the integration from YAML (no-op here)."""
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
