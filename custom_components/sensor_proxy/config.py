"""Configuration helpers for the Sensor Proxy integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .const import (
    CONF_CREATE_UTILITY_METERS,
    CONF_UTILITY_METER_TYPES,
    DEFAULT_CREATE_UTILITY_METERS,
    DEFAULT_UTILITY_METER_TYPES,
)


@dataclass(frozen=True)
class UtilityOptions:
    """Resolved utility meter configuration for a proxy sensor."""

    create: bool
    meter_types: tuple[str, ...]
    name_template: str | None
    unique_id_template: str | None


def _resolve_meter_types(candidate: Sequence[str] | None) -> tuple[str, ...]:
    if not candidate:
        return tuple(DEFAULT_UTILITY_METER_TYPES)
    return tuple(candidate)


def build_utility_options(
    config: Mapping[str, Any],
    domain_data: Mapping[str, Any],
) -> UtilityOptions:
    """Return per-proxy utility meter options, merging globals with overrides."""

    create_default = domain_data.get(
        CONF_CREATE_UTILITY_METERS, DEFAULT_CREATE_UTILITY_METERS
    )
    meter_default: Sequence[str] = domain_data.get(
        CONF_UTILITY_METER_TYPES, DEFAULT_UTILITY_METER_TYPES
    )

    create_value = config.get(CONF_CREATE_UTILITY_METERS)
    if create_value is None:
        create_value = create_default

    meter_types = config.get(CONF_UTILITY_METER_TYPES) or meter_default

    return UtilityOptions(
        create=bool(create_value),
        meter_types=_resolve_meter_types(meter_types),
        name_template=config.get("utility_name_template"),
        unique_id_template=config.get("utility_unique_id_template"),
    )
