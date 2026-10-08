from typing import Any

from homeassistant.components.switch import SwitchEntity
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
            yield MyAir3ZoneSwitch(coordinator, zone_id)

    setup_zone_entities(entry, async_add_entities, zone_entities)


class MyAir3ZoneSwitch(MyAir3ZoneEntity, SwitchEntity):
    """Opens or closes a zone that has no temperature sensor."""

    def __init__(self, coordinator: MyAir3Coordinator, zone_id: int):
        super().__init__(coordinator, zone_id, "switch")

    @property
    def name(self) -> str:
        return self.zone_name

    @property
    def is_on(self) -> bool:
        return self.zone["setting"] == "1"

    @handle_errors
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.client.set_zone_data(self.zone_id, zoneSetting="1")

    @handle_errors
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.client.set_zone_data(self.zone_id, zoneSetting="0")
