from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MyAir3ConfigEntry, MyAir3Coordinator
from .entity import MyAir3Entity, MyAir3ZoneEntity, setup_zone_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyAir3ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([MyAir3FaultSensor(entry.runtime_data)])

    def zone_entities(coordinator: MyAir3Coordinator, zone_id: int, zone: dict):
        yield MyAir3ZoneMotorError(coordinator, zone_id)
        if zone["has_climate_control"]:
            # Only zones with a wireless temperature sensor have a battery.
            yield MyAir3ZoneLowBattery(coordinator, zone_id)

    setup_zone_entities(entry, async_add_entities, zone_entities)


class MyAir3FaultSensor(MyAir3Entity, BinarySensorEntity):
    """On when the air conditioner reports an error code."""

    _attr_name = "Fault"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: MyAir3Coordinator):
        super().__init__(coordinator, "fault")

    @property
    def is_on(self) -> bool:
        return bool(self.system["error_code"])

    @property
    def extra_state_attributes(self) -> dict:
        return {"error_code": self.system["error_code"] or None}


class MyAir3ZoneMotorError(MyAir3ZoneEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: MyAir3Coordinator, zone_id: int):
        super().__init__(coordinator, zone_id, "motor_error")

    @property
    def name(self) -> str:
        return f"{self.zone_name} damper motor"

    @property
    def is_on(self) -> bool:
        return self.zone["motor_error"]


class MyAir3ZoneLowBattery(MyAir3ZoneEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: MyAir3Coordinator, zone_id: int):
        super().__init__(coordinator, zone_id, "low_battery")

    @property
    def name(self) -> str:
        return f"{self.zone_name} sensor battery"

    @property
    def is_on(self) -> bool:
        return self.zone["low_battery"]
