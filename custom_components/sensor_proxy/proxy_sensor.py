"""Sensor entity that mirrors the state of another entity."""

from __future__ import annotations

import logging
from typing import Callable, Iterable, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.start import async_at_started
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
        create_utility_meters: Optional[bool] = None,
        utility_meter_types: Optional[Iterable[str]] = None,
        utility_name_template: Optional[str] = None,
        utility_unique_id_template: Optional[str] = None,
    ) -> None:
        self._hass = hass
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._source_entity_id = source_entity_id
        self._device_id = device_id
        self._unsub: Optional[Callable[[], None]] = None
        self._create_utility_meters = create_utility_meters  # None = use global default
        self._utility_meter_types = utility_meter_types
        self._utility_name_template = utility_name_template
        self._utility_unique_id_template = utility_unique_id_template
        self._created_meter_entities: list[tuple[str, str | None]] = []
        self._utility_meters_created = False

        # Default HA entity attributes; ensure they exist even if the source
        # entity is missing at initialization to avoid AttributeError on access.
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}
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

        if self._device_id:
            if not self.unique_id:
                _LOGGER.warning(
                    "Device ID provided for %s but no unique_id specified. Device association requires a unique_id. "
                    "Please add a unique_id to your configuration.",
                    self.name or self._source_entity_id,
                )
            else:
                entity_registry = er.async_get(self.hass)
                # Associate with device; registry does not accept 'suggested_area_id'
                entity_registry.async_get_or_create(
                    "sensor",
                    "sensor_proxy",
                    self.unique_id,
                    device_id=self._device_id,
                )

        self._unsub = async_track_state_change_event(
            self.hass, self._source_entity_id, self._async_source_changed_event
        )

        # Attempt to initialize from the current source state (helps restored proxies)
        try:
            self.update()
        except Exception:
            _LOGGER.exception(
                "Failed to initialize proxy %s from source on add", self.name
            )

        # Informative debug: the proxy entity is now present in hass and listening
        _LOGGER.debug(
            "Proxy sensor created: name=%s unique_id=%s source=%s device_id=%s available=%s",
            self.name,
            self.unique_id,
            self._source_entity_id,
            self._device_id,
            self.available,
        )

        # Don't create utility meters here - wait until source is available
        # Utility meters will be created on first successful state copy

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

    def _copy_source_attributes(self, source_state) -> None:
        prev_available = self._attr_available

        if source_state is None or source_state.state in ("unavailable", "unknown"):
            # Mark as unavailable only if it changed to reduce log spam
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            self._attr_native_unit_of_measurement = None
            self._attr_device_class = None
            self._attr_state_class = None
            self._attr_icon = None
            self._attr_available = False
            if prev_available:
                _LOGGER.info(
                    "Proxy %s marked unavailable (source=%s)",
                    self.name,
                    self._source_entity_id,
                )
            return

        # Copy attributes from source and log initialization only when availability changes
        self._attr_available = True
        self._attr_native_value = source_state.state
        self._attr_extra_state_attributes = source_state.attributes.copy()

        attrs = source_state.attributes
        self._attr_native_unit_of_measurement = attrs.get("unit_of_measurement")
        self._attr_device_class = attrs.get("device_class")
        self._attr_state_class = attrs.get("state_class")
        self._attr_icon = attrs.get("icon")

        if not prev_available:
            _LOGGER.info(
                "Proxy %s initialized from source %s: state=%s",
                self.name,
                self._source_entity_id,
                self._attr_native_value,
            )
            # Write state to ensure unit is available before creating utility meters
            self.async_write_ha_state()
            # Create utility meters once when first initialized
            # Check if we should create utility meters
            should_create = self._create_utility_meters or (
                self._create_utility_meters is None
                and self._hass.data.get(DOMAIN_CONST, {}).get(
                    "create_utility_meters", False
                )
            )
            if should_create and not self._utility_meters_created:
                self._utility_meters_created = True

                # Use async_at_started to wait for Home Assistant to be fully ready
                # This ensures the state machine is initialized and source entity state is available
                # This is the official pattern used by utility_meter and other core components
                @callback
                def _create_meters_when_ready(_hass: HomeAssistant) -> None:
                    """Create utility meters when Home Assistant is fully started."""
                    self._hass.async_create_task(self._async_create_utility_meters())

                self.async_on_remove(
                    async_at_started(self._hass, _create_meters_when_ready)
                )

    @callback
    def _async_source_changed(self, entity_id, old_state, new_state) -> None:
        if new_state is None:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
        else:
            self._copy_source_attributes(new_state)

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
            _LOGGER.warning(
                "Platform unavailable for %s; skipping utility meter creation",
                self.entity_id,
            )
            return

        meter_types = self._utility_meter_types or self._hass.data.get(
            DOMAIN_CONST, {}
        ).get(CONF_UTILITY_METER_TYPES, DEFAULT_UTILITY_METER_TYPES)

        _LOGGER.info(
            "Attempting to create utility meters for %s with types: %s",
            self.entity_id,
            meter_types,
        )

        # Verify that our proxy state is actually in the state machine
        proxy_state = self._hass.states.get(self.entity_id)
        if not proxy_state or not proxy_state.attributes.get("unit_of_measurement"):
            _LOGGER.warning(
                "Proxy %s state not fully available yet (unit=%s), skipping utility meter creation",
                self.entity_id,
                (
                    proxy_state.attributes.get("unit_of_measurement")
                    if proxy_state
                    else "no state"
                ),
            )
            return

        # Defer default name generation until we have the proxy object id to avoid
        # duplicating prefixes for glob-created proxies
        # (e.g. avoid 'sensor.copy_energy_meter_copy_energy_meter_daily' when the desired
        # name is 'sensor.copy_energy_meter_daily')
        source_state = self._hass.states.get(self._source_entity_id)
        if not source_state:
            _LOGGER.warning(
                "Source entity %s not found when creating utility meters for %s",
                self._source_entity_id,
                self.entity_id,
            )
            return

        entity_registry = er.async_get(self._hass)
        hass_data = self._hass.data.setdefault(DOMAIN_CONST, {})
        hass_data.setdefault("created_utility_meters", {})

        # Register this parent meter in utility meter component's data structure
        # This is required for the utility meter sensors to find their parent
        from homeassistant.components.utility_meter.const import (
            DATA_TARIFF_SENSORS,
            DATA_UTILITY,
        )

        self._hass.data.setdefault(DATA_UTILITY, {})
        if self.entity_id not in self._hass.data[DATA_UTILITY]:
            self._hass.data[DATA_UTILITY][self.entity_id] = {}
        self._hass.data[DATA_UTILITY][self.entity_id][DATA_TARIFF_SENSORS] = []
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
        # Only create utility meters for energy accumulators reporting a
        # total_increasing state_class and device_class == energy.
        state_class = attrs.get("state_class")
        device_class = attrs.get("device_class")

        # StrEnum can be compared directly with strings
        if (
            state_class
            not in (SensorStateClass.TOTAL, SensorStateClass.TOTAL_INCREASING)
        ) or (device_class != SensorDeviceClass.ENERGY):
            # Only log if utility meters were explicitly enabled for this entity
            if self._create_utility_meters is not None:
                _LOGGER.info(
                    "Skipping utility meter creation for %s: source %s has state_class=%s, device_class=%s "
                    "(requires state_class=total/total_increasing and device_class=energy)",
                    self.entity_id,
                    self._source_entity_id,
                    state_class,
                    device_class,
                )
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
            # Register the meter in the parent meter's sensor list
            self._hass.data[DATA_UTILITY][self.entity_id][DATA_TARIFF_SENSORS].append(
                utility_meter
            )
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

        # Clean up utility meter component registration
        from homeassistant.components.utility_meter.const import DATA_UTILITY

        if (
            DATA_UTILITY in self.hass.data
            and self.entity_id in self.hass.data[DATA_UTILITY]
        ):
            self.hass.data[DATA_UTILITY].pop(self.entity_id, None)

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
