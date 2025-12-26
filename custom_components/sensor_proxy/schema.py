"""Configuration schema for the Sensor Proxy integration."""

from __future__ import annotations

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID

from .const import (
    CONF_CREATE_UTILITY_METERS,
    CONF_UTILITY_METER_TYPES,
)

__all__ = ["PLATFORM_SCHEMA"]


# Schema for individual sensors in multi-entity configuration
SENSOR_ITEM_SCHEMA = vol.Schema(
    {
        vol.Required("suffix"): cv.string,
        vol.Optional("source_entity_id"): cv.entity_id,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_CREATE_UTILITY_METERS): cv.boolean,
        vol.Optional(CONF_UTILITY_METER_TYPES): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("utility_name_template"): cv.string,
        vol.Optional("utility_unique_id_template"): cv.string,
    }
)

# Single entity schema (legacy/simple format)
SINGLE_ENTITY_SCHEMA = {
    vol.Required("source_entity_id"): cv.entity_id,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional("device_id"): cv.string,
    vol.Optional(CONF_CREATE_UTILITY_METERS): cv.boolean,
    vol.Optional(CONF_UTILITY_METER_TYPES): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional("utility_name_template"): cv.string,
    vol.Optional("utility_unique_id_template"): cv.string,
}

# Multi-entity schema (new compact format)
MULTI_ENTITY_SCHEMA = {
    vol.Required("source_base"): cv.string,
    vol.Optional("name_base"): cv.string,
    vol.Optional("unique_id_base"): cv.string,
    vol.Optional("device_id"): cv.string,
    vol.Required("sensors"): vol.All(cv.ensure_list, [SENSOR_ITEM_SCHEMA]),
}


def validate_platform_schema(config):
    """Validate that exactly one of the two formats is used."""
    has_single = "source_entity_id" in config
    has_multi = "source_base" in config

    if has_single and has_multi:
        raise vol.Invalid(
            "Cannot use both 'source_entity_id' and 'source_base' in the same config"
        )
    if not has_single and not has_multi:
        raise vol.Invalid(
            "Must provide either 'source_entity_id' (single entity) or 'source_base' (multi-entity)"
        )

    if has_single:
        validated_config = vol.Schema(SINGLE_ENTITY_SCHEMA, extra=vol.ALLOW_EXTRA)(
            config
        )
        # Require at least name or unique_id for single entity
        if not validated_config.get(CONF_NAME) and not validated_config.get(
            CONF_UNIQUE_ID
        ):
            raise vol.Invalid(
                "Must provide at least 'name' or 'unique_id' (preferably both) for single entity configuration"
            )
        return validated_config
    else:
        validated_config = vol.Schema(MULTI_ENTITY_SCHEMA, extra=vol.ALLOW_EXTRA)(
            config
        )
        # Require at least name_base or unique_id_base for multi-entity
        if not validated_config.get("name_base") and not validated_config.get(
            "unique_id_base"
        ):
            raise vol.Invalid(
                "Must provide at least 'name_base' or 'unique_id_base' (preferably both) for multi-entity configuration"
            )
        return validated_config


PLATFORM_SCHEMA = vol.Schema(validate_platform_schema)
