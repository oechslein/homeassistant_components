from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
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
    hass.data[DOMAIN].setdefault("bus_listeners", [])
    hass.data[DOMAIN].setdefault("glob_listeners", {})
    hass.data[DOMAIN].setdefault("glob_listener_active_keys", set())
    hass.data[DOMAIN].setdefault("glob_listener_cleanup_handle", None)

    async def _cleanup_listeners(event):
        listeners = hass.data[DOMAIN]["bus_listeners"]
        for unsub in list(listeners):
            unsub()
        listeners.clear()
        hass.data[DOMAIN]["glob_listeners"].clear()
        hass.data[DOMAIN]["glob_listener_active_keys"].clear()
        hass.data[DOMAIN]["glob_listener_cleanup_handle"] = None

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _cleanup_listeners)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry created via the UI."""
    # Forward the config entry to the sensor platform
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")
