from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MyAir3ConfigEntry, MyAir3Coordinator
from .entity import MyAir3Entity, MyAir3ZoneEntity, setup_zone_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyAir3ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([MyAir3CentralTemperature(entry.runtime_data)])

    def zone_entities(coordinator: MyAir3Coordinator, zone_id: int, zone: dict):
        if zone["has_climate_control"]:
            yield MyAir3ZoneTemperature(coordinator, zone_id)
            yield MyAir3ZoneSignal(coordinator, zone_id)

    setup_zone_entities(entry, async_add_entities, zone_entities)


class _MyAir3TemperatureSensor(SensorEntity):
    """Kept as its own entity so Home Assistant records long-term statistics for it."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1


class MyAir3CentralTemperature(MyAir3Entity, _MyAir3TemperatureSensor):
    """Temperature measured at the central unit's sensor."""

    _attr_name = "Temperature"

    def __init__(self, coordinator: MyAir3Coordinator):
        super().__init__(coordinator, "temperature")

    @property
    def native_value(self) -> float | None:
        return self.system["actual_temp"]


class MyAir3ZoneTemperature(MyAir3ZoneEntity, _MyAir3TemperatureSensor):
    def __init__(self, coordinator: MyAir3Coordinator, zone_id: int):
        super().__init__(coordinator, zone_id, "temperature")

    @property
    def name(self) -> str:
        return f"{self.zone_name} temperature"

    @property
    def native_value(self) -> float | None:
        return self.zone["actual_temp"]


class MyAir3ZoneSignal(MyAir3ZoneEntity, SensorEntity):
    """Wireless signal strength of a zone's temperature sensor, as the controller reports it."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:wifi"

    def __init__(self, coordinator: MyAir3Coordinator, zone_id: int):
        super().__init__(coordinator, zone_id, "rf_strength")

    @property
    def name(self) -> str:
        return f"{self.zone_name} sensor signal"

    @property
    def native_value(self) -> int:
        return self.zone["rf_strength"]
