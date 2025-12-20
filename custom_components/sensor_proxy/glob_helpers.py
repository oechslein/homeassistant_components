"""Helper functions for glob listener management."""

from __future__ import annotations

import fnmatch
from collections.abc import Iterable
from typing import Any
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "build_glob_listener_key",
    "matches_patterns",
    "render_template",
    "schedule_glob_listener_cleanup",
]


def render_template(template: str | None, entity_id: str) -> str:
    """Render a simple template replacing '*' with the object_id."""
    if not template:
        return ""
    object_id = entity_id.split(".", 1)[1]
    return template.replace("*", object_id)


def matches_patterns(
    object_id: str,
    include: Iterable[str] | None,
    exclude: Iterable[str] | None,
) -> bool:
    """Return True if object_id matches the include/exclude patterns.

    Adds debug logging to show which patterns matched or caused rejection.
    Accepts a single pattern string as well as iterables.
    """
    _LOGGER.debug(
        "matching object_id=%s include=%r exclude=%r",
        object_id,
        include,
        exclude,
    )

    # Normalize single string patterns to lists
    if isinstance(include, str):
        include = [include]
    if isinstance(exclude, str):
        exclude = [exclude]

    try:
        if include:
            matched_any = any(
                fnmatch.fnmatchcase(object_id, pattern) for pattern in include
            )
            _LOGGER.debug(
                "include matched=%s for object_id=%s (patterns=%r)",
                matched_any,
                object_id,
                include,
            )
            if not matched_any:
                return False

        if exclude:
            excluded = any(
                fnmatch.fnmatchcase(object_id, pattern) for pattern in exclude
            )
            _LOGGER.debug(
                "exclude matched=%s for object_id=%s (patterns=%r)",
                excluded,
                object_id,
                exclude,
            )
            if excluded:
                return False

        return True
    except Exception as exc:  # Defensive: log and treat as non-match
        _LOGGER.exception(
            "Error matching patterns for object_id=%s include=%r exclude=%r: %s",
            object_id,
            include,
            exclude,
            exc,
        )
        return False


def build_glob_listener_key(
    source_glob: str,
    include_patterns: Iterable[str] | None,
    exclude_patterns: Iterable[str] | None,
    name_template: str | None,
    unique_template: str | None,
    create_utility_meters: bool,
    utility_meter_types: Iterable[str] | None,
    utility_name_template: str | None,
    utility_unique_id_template: str | None,
    device_id: str | None,
) -> tuple[Any, ...]:
    """Build a stable, hashable key representing a glob listener configuration."""
    return (
        source_glob,
        tuple(include_patterns or ()),
        tuple(exclude_patterns or ()),
        name_template,
        unique_template,
        bool(create_utility_meters),
        tuple(utility_meter_types or ()),
        utility_name_template,
        utility_unique_id_template,
        device_id,
    )




def schedule_glob_listener_cleanup(hass: HomeAssistant, domain_data: dict) -> None:
    """Schedule removal of unused glob listeners."""
    if domain_data.get("glob_listener_cleanup_handle"):
        return

    async def _run_cleanup(_now):
        store = domain_data.get("glob_listeners", {})
        active_keys = domain_data.get("glob_listener_active_keys", set())
        bus_listeners = domain_data.get("bus_listeners", [])
        for key, entry in list(store.items()):
            if key in active_keys:
                continue
            if entry.get("refcount", 0) > 0:
                continue
            _LOGGER.debug("Cleaning up glob listener key: %s", key)
            unsub = entry.get("unsubscribe")
            if unsub:
                if unsub in bus_listeners:
                    bus_listeners.remove(unsub)
                _LOGGER.debug("Unsubscribing glob listener for key: %s", key)
                unsub()
            store.pop(key, None)
        active_keys.clear()
        domain_data["glob_listener_cleanup_handle"] = None

    domain_data["glob_listener_cleanup_handle"] = async_call_later(
        hass, 0, _run_cleanup
    )
