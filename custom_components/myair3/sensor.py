from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MyAir3ConfigEntry, MyAir3Coordinator
from .entity import MyAir3ZoneEntity, setup_zone_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyAir3ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    def zone_entities(coordinator: MyAir3Coordinator, zone_id: int, zone: dict):
        if zone["has_climate_control"]:
            yield MyAir3ZoneSignal(coordinator, zone_id)

    setup_zone_entities(entry, async_add_entities, zone_entities)


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
