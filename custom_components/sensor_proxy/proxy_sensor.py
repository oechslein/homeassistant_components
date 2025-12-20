"""Sensor entity that mirrors the state of another entity."""

from __future__ import annotations

import logging
from typing import Any, Iterable, Optional, Tuple

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import slugify

from .const import (
    CONF_UTILITY_METER_TYPES,
    DEFAULT_UTILITY_METER_TYPES,
)
from .const import DOMAIN as DOMAIN_CONST
from .virtual_meter import build_virtual_meter_entity

_LOGGER = logging.getLogger(__name__)


class SensorProxySensor(SensorEntity):
    """Sensor entity that mirrors another sensor's state and attributes."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: Optional[str],
        source_entity_id: str,
        unique_id: Optional[str],
        device_id: Optional[str] = None,
        create_utility_meters: bool = False,
        utility_meter_types: Optional[Iterable[str]] = None,
        utility_name_template: Optional[str] = None,
        utility_unique_id_template: Optional[str] = None,
        glob_listener_key: Optional[Tuple[Any, ...]] = None,
    ) -> None:
        self._hass = hass
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._source_entity_id = source_entity_id
        self._device_id = device_id
        self._unsub = None
        self._create_utility_meters = create_utility_meters
        self._utility_meter_types = utility_meter_types
        self._utility_name_template = utility_name_template
        self._utility_unique_id_template = utility_unique_id_template
        self._created_meter_entities: list[tuple[str, str | None]] = []
        self._glob_listener_key = glob_listener_key
        self._glob_listener_attached = False

        # Default HA entity attributes; ensure they exist even if the source
        # entity is missing at initialization to avoid AttributeError on access.
        self._attr_native_value = None
        self._attr_extra_state_attributes = None
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None
        self._attr_state_class = None
        self._attr_icon = None
        self._attr_available = False

        source_state = hass.states.get(self._source_entity_id)
        if source_state:
            self._copy_source_attributes(source_state)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._claim_glob_listener()

        if self._device_id:
            entity_registry = er.async_get(self.hass)
            source_entry = entity_registry.async_get(self._source_entity_id)
            area_id = source_entry.area_id if source_entry else None
            entity_registry.async_get_or_create(
                "sensor",
                "sensor_proxy",
                self.unique_id,
                device_id=self._device_id,
                suggested_area_id=area_id,
            )

        self._unsub = async_track_state_change_event(
            self.hass, self._source_entity_id, self._async_source_changed_event
        )

        # Informative debug: the proxy entity is now present in hass and listening
        _LOGGER.debug(
            "Proxy sensor created: name=%s unique_id=%s source=%s device_id=%s device_class=%s state_class=%s available=%s",
            self.name,
            self.unique_id,
            self._source_entity_id,
            self._device_id,
            self._attr_device_class,
            self._attr_state_class,
            self.available,
        )

        if self._create_utility_meters:
            await self._async_create_utility_meters()

    async def async_will_remove_from_hass(self) -> None:
        # Debug: proxy is being removed from hass
        _LOGGER.debug(
            "Removing proxy sensor: name=%s unique_id=%s entity_id=%s source=%s",
            self.name,
            self.unique_id,
            self.entity_id,
            self._source_entity_id,
        )

        if self._unsub:
            self._unsub()
            self._unsub = None
        await self._async_cleanup_created_meters()
        self._release_glob_listener()

    def _copy_source_attributes(self, source_state) -> None:
        if source_state is None or source_state.state in ("unavailable", "unknown"):
            _LOGGER.debug(
                "Source unavailable for proxy %s (source=%s): state=%s",
                self.name,
                self._source_entity_id,
                None if source_state is None else source_state.state,
            )
            self._attr_native_value = None
            self._attr_extra_state_attributes = None
            self._attr_native_unit_of_measurement = None
            self._attr_device_class = None
            self._attr_state_class = None
            self._attr_icon = None
            self._attr_available = False
            return

        self._attr_available = True
        self._attr_native_value = source_state.state
        self._attr_extra_state_attributes = source_state.attributes.copy()

        attrs = source_state.attributes
        self._attr_native_unit_of_measurement = attrs.get("unit_of_measurement")
        self._attr_device_class = attrs.get("device_class")
        self._attr_state_class = attrs.get("state_class")
        self._attr_icon = attrs.get("icon")

        # Debug: show the copied attribute snapshot for visibility in logs
        _LOGGER.debug(
            "Proxy %s copied attributes from %s: state=%s device_class=%s state_class=%s unit=%s available=%s",
            self.name,
            self._source_entity_id,
            self._attr_native_value,
            self._attr_device_class,
            self._attr_state_class,
            self._attr_native_unit_of_measurement,
            self._attr_available,
        )

    @callback
    def _async_source_changed(self, entity_id, old_state, new_state) -> None:
        _LOGGER.debug(
            "Source state change for proxy %s: source=%s old=%s new=%s",
            self.name,
            entity_id,
            None if old_state is None else old_state.state,
            None if new_state is None else new_state.state,
        )

        if new_state is None:
            self._attr_native_value = None
            self._attr_extra_state_attributes = None
        else:
            self._copy_source_attributes(new_state)

        # Debug: report resulting availability and key attrs after handling
        _LOGGER.debug(
            "Proxy %s state after update: state=%s device_class=%s state_class=%s available=%s",
            self.name,
            self._attr_native_value,
            self._attr_device_class,
            self._attr_state_class,
            self._attr_available,
        )

        self.async_write_ha_state()

    @callback
    def _async_source_changed_event(self, event) -> None:
        data = event.data
        entity_id = data.get("entity_id")
        old_state = data.get("old_state")
        new_state = data.get("new_state")
        self._async_source_changed(entity_id, old_state, new_state)

    def update(self) -> None:
        source_state = self._hass.states.get(self._source_entity_id)
        if source_state:
            self._copy_source_attributes(source_state)

    async def _async_create_utility_meters(self) -> None:
        platform = self.platform
        if not platform:
            _LOGGER.debug("Platform unavailable; skipping utility meter creation")
            return

        meter_types = self._utility_meter_types or self._hass.data.get(
            DOMAIN_CONST, {}
        ).get(CONF_UTILITY_METER_TYPES, DEFAULT_UTILITY_METER_TYPES)

        # Defer default name generation until we have the proxy object id to avoid
        # duplicating prefixes for glob-created proxies (e.g. avoid 'copy2_copy2_xxx').
        source_state = self._hass.states.get(self._source_entity_id)
        if not source_state:
            return

        entity_registry = er.async_get(self._hass)
        hass_data = self._hass.data.setdefault(DOMAIN_CONST, {})
        hass_data.setdefault("created_utility_meters", {})
        base_object_id = (
            self.entity_id.split(".", 1)[1]
            if self.entity_id
            else slugify(self._attr_unique_id or self._attr_name or "sensor_proxy")
        )

        # Choose defaults based on the resolved object id to avoid duplicated prefixes
        name_template = self._utility_name_template or f"{base_object_id}_{{cycle}}"
        unique_id_template = self._utility_unique_id_template or (
            f"{self._attr_unique_id}_{{cycle}}"
            if self._attr_unique_id
            else f"{base_object_id}_{{cycle}}"
        )

        attrs = source_state.attributes
        if (
            attrs.get("state_class") != "total_increasing"
            or attrs.get("device_class") != "energy"
        ):
            return

        meters_to_add = []
        for meter_type in meter_types:
            meter_name = name_template.replace("*", base_object_id).replace(
                "{cycle}", meter_type
            )
            meter_unique_id = unique_id_template.replace("*", base_object_id).replace(
                "{cycle}", meter_type
            )
            if meter_unique_id:
                existing = entity_registry.async_get_entity_id(
                    domain="sensor",
                    platform="utility_meter",
                    unique_id=meter_unique_id,
                )
                if existing and self._hass.states.get(existing):
                    _LOGGER.debug("Utility meter exists, skipping: %s", meter_unique_id)
                    continue

            utility_meter, meter_entity_id = build_virtual_meter_entity(
                hass=self._hass,
                source_entity_id=self._source_entity_id,
                parent_entity_id=self.entity_id,
                base_object_id=base_object_id,
                meter_type=meter_type,
                meter_name=meter_name,
                meter_unique_id=meter_unique_id,
            )
            meters_to_add.append(utility_meter)
            self._created_meter_entities.append((meter_entity_id, meter_unique_id))
            if meter_unique_id:
                hass_data["created_utility_meters"][meter_unique_id] = meter_entity_id

        if meters_to_add:
            await platform.async_add_entities(meters_to_add)

            # Debug: list created meters with key details
            _LOGGER.debug(
                "Created %d utility meter(s) for %s: %s",
                len(meters_to_add),
                self.entity_id,
                [
                    {
                        "entity_id": m.entity_id,
                        "unique_id": getattr(m, "unique_id", None),
                        "meter_type": getattr(m, "meter_type", None),
                    }
                    for m in meters_to_add
                ],
            )

    async def _async_cleanup_created_meters(self) -> None:
        if not self._created_meter_entities:
            return
        entity_registry = er.async_get(self.hass)
        hass_data = self.hass.data.get(DOMAIN_CONST, {})
        created = hass_data.get("created_utility_meters", {})
        platform = self.platform
        for entity_id, unique_id in list(self._created_meter_entities):
            _LOGGER.debug(
                "Cleaning up created utility meter: entity_id=%s unique_id=%s parent=%s",
                entity_id,
                unique_id,
                self.entity_id,
            )
            if platform:
                try:
                    await platform.async_remove_entity(entity_id)
                    _LOGGER.debug("Platform removed utility meter: %s", entity_id)
                except ValueError:
                    _LOGGER.debug(
                        "Platform reported ValueError removing utility meter (may already be gone): %s",
                        entity_id,
                    )
            if entity_registry.async_get(entity_id):
                entity_registry.async_remove(entity_id)
                _LOGGER.debug("Entity registry removed utility meter: %s", entity_id)
            if unique_id and unique_id in created:
                created.pop(unique_id)
        self._created_meter_entities.clear()

    def _claim_glob_listener(self) -> None:
        if not self._glob_listener_key or self._glob_listener_attached:
            return
        domain = self._hass.data.get(DOMAIN_CONST, {})
        store = domain.get("glob_listeners")
        if not store:
            return
        entry = store.get(self._glob_listener_key)
        if not entry:
            return
        entry["refcount"] = entry.get("refcount", 0) + 1
        self._glob_listener_attached = True

    def _release_glob_listener(self) -> None:
        if not self._glob_listener_key or not self._glob_listener_attached:
            return
        domain = self._hass.data.get(DOMAIN_CONST, {})
        store = domain.get("glob_listeners")
        if not store or self._glob_listener_key not in store:
            self._glob_listener_attached = False
            return
        entry = store[self._glob_listener_key]
        entry["refcount"] = max(0, entry.get("refcount", 1) - 1)
        _LOGGER.debug(
            "Released glob listener: key=%s new_refcount=%d",
            self._glob_listener_key,
            entry.get("refcount", 0),
        )
        if entry["refcount"] > 0:
            self._glob_listener_attached = False
            return
        _LOGGER.debug("Removing glob listener key: %s", self._glob_listener_key)
        store.pop(self._glob_listener_key, None)
        active_keys = domain.get("glob_listener_active_keys")
        if active_keys and self._glob_listener_key in active_keys:
            active_keys.discard(self._glob_listener_key)
        unsub = entry.get("unsubscribe")
        if unsub:
            bus_list = domain.get("bus_listeners", [])
            if unsub in bus_list:
                bus_list.remove(unsub)
            _LOGGER.debug(
                "Unsubscribing glob listener callback for key: %s",
                self._glob_listener_key,
            )
            unsub()
        self._glob_listener_attached = False
