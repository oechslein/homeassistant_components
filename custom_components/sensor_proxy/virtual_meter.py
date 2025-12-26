"""Utility meter helpers for the Sensor Proxy integration."""

from __future__ import annotations

import logging
from typing import Any, Tuple

from homeassistant.components.utility_meter import DEFAULT_OFFSET
from homeassistant.components.utility_meter.sensor import UtilityMeterSensor

__all__ = [
    "VirtualUtilityMeter",
    "UTILITY_METER_ALLOWED_KWARGS",
    "build_virtual_meter_entity",
]

_LOGGER = logging.getLogger(__name__)

UTILITY_METER_ALLOWED_KWARGS = {
    "hass",
    "source_entity",
    "name",
    "meter_type",
    "meter_offset",
    "net_consumption",
    "tariff",
    "tariff_entity",
    "parent_meter",
    "delta_values",
    "cron_pattern",
    "periodically_resetting",
    "sensor_always_available",
    "unique_id",
}


class VirtualUtilityMeter(UtilityMeterSensor):
    """Thin wrapper around UtilityMeterSensor to expose unique_id."""

    def __init__(self, **kwargs: Any) -> None:
        allowed_kwargs = {
            key: value
            for key, value in kwargs.items()
            if key in UTILITY_METER_ALLOWED_KWARGS
        }
        super().__init__(**allowed_kwargs)
        # Ensure the utility meter does not inherit a mismatched device_class from its source.
        # Utility meters are totalizing sensors; to avoid home assistant warnings about
        # incompatible device_class/state_class combinations, explicitly clear device_class.
        self._attr_device_class = None
        self._attr_unique_id = kwargs.get("unique_id")

    @property
    def unique_id(self) -> str | None:
        return self._attr_unique_id


def build_virtual_meter_entity(
    hass,
    source_entity_id: str,
    parent_entity_id: str | None,
    base_object_id: str,
    meter_type: str,
    meter_name: str,
    meter_unique_id: str | None,
) -> Tuple[VirtualUtilityMeter, str]:
    """Create a configured VirtualUtilityMeter and assign an entity_id.

    Following powercalc's pattern: directly build entity_id without async_generate_entity_id.
    The entity registry will handle conflicts when the entity is added to Home Assistant.
    """

    # Build the entity_id directly, like powercalc does
    # This avoids _2 suffix issues caused by async_generate_entity_id checking state machine
    meter_entity_id = f"sensor.{base_object_id}_{meter_type}"

    _LOGGER.debug(
        "Building utility meter: entity_id=%s unique_id=%s",
        meter_entity_id,
        meter_unique_id,
    )
    # Utility meters must track the proxy entity, not the original source
    params: dict[str, Any] = {
        "hass": hass,
        "source_entity": parent_entity_id,  # Track the proxy, not the original source
        "name": meter_name,
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
        "unique_id": meter_unique_id,
    }
    utility_meter = VirtualUtilityMeter(**params)
    utility_meter.entity_id = meter_entity_id

    # Debug output for created virtual meter
    _LOGGER.debug(
        "Built virtual utility meter: name=%s entity_id=%s unique_id=%s meter_type=%s source=%s",
        params.get("name"),
        meter_entity_id,
        params.get("unique_id"),
        meter_type,
        parent_entity_id,
    )

    return utility_meter, meter_entity_id
