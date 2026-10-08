from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MyAir3ConfigEntry, MyAir3Coordinator
from .entity import MyAir3ZoneEntity, handle_errors, setup_zone_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyAir3ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    def zone_entities(coordinator: MyAir3Coordinator, zone_id: int, zone: dict):
        if not zone["has_climate_control"]:
            yield MyAir3ZoneDamper(coordinator, zone_id)

    setup_zone_entities(entry, async_add_entities, zone_entities)


class MyAir3ZoneDamper(MyAir3ZoneEntity, NumberEntity):
    """Damper opening for a zone that has no temperature sensor."""

    _attr_native_step = 5
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:valve"

    def __init__(self, coordinator: MyAir3Coordinator, zone_id: int):
        super().__init__(coordinator, zone_id, "damper")

    @property
    def name(self) -> str:
        return f"{self.zone_name} damper"

    @property
    def native_min_value(self) -> float:
        return self.zone["min_damper"]

    @property
    def native_max_value(self) -> float:
        return self.zone["max_damper"]

    @property
    def native_value(self) -> float:
        return self.zone["damper"]

    @handle_errors
    async def async_set_native_value(self, value: float) -> None:
        value = min(max(int(value), self.native_min_value), self.native_max_value)
        await self.client.set_zone_data(self.zone_id, userPercentSetting=str(int(value)))
