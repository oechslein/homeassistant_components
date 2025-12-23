"""Configuration schema for the Sensor Proxy integration."""

from __future__ import annotations

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
)
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID

from .const import (
    CONF_CREATE_UTILITY_METERS,
    CONF_UTILITY_METER_TYPES,
)

__all__ = ["PLATFORM_SCHEMA"]


PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required("source_entity_id"): cv.entity_id,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional("device_id"): cv.string,
        vol.Optional(CONF_CREATE_UTILITY_METERS): cv.boolean,
        vol.Optional(CONF_UTILITY_METER_TYPES): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("utility_name_template"): cv.string,
        vol.Optional("utility_unique_id_template"): cv.string,
    }
)
