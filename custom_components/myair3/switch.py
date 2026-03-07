from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    client = hass.data[DOMAIN][entry.entry_id]["client"]
    entities = []

    for zone_id, zone_data in coordinator.data.get("zones", {}).items():
        if zone_data.get("actualTemp") is None:
            entities.append(MyAir3ZoneSwitch(coordinator, client, zone_id))

    async_add_entities(entities)

class MyAir3ZoneSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, client, zone_id):
        super().__init__(coordinator)
        self.client = client
        self.zone_id = zone_id
        self._attr_unique_id = f"{client.ip}_zone_{zone_id}_switch"

    @property
    def name(self):
        return f"{self.coordinator.data['zones'][self.zone_id]['name']} Switch"

    @property
    def is_on(self):
        return self.coordinator.data["zones"][self.zone_id]["setting"] == "1"

    async def async_turn_on(self, **kwargs):
        await self.client.set_zone_data(self.zone_id, "zoneSetting", "1")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        await self.client.set_zone_data(self.zone_id, "zoneSetting", "0")
        await self.coordinator.async_request_refresh()
