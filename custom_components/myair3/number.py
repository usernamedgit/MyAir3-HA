from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    client = hass.data[DOMAIN][entry.entry_id]["client"]
    entities = []

    for zone_id, zone_data in coordinator.data.get("zones", {}).items():
        if zone_data.get("actualTemp") is None:
            entities.append(MyAir3ZoneDamper(coordinator, client, zone_id))

    async_add_entities(entities)

class MyAir3ZoneDamper(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 5

    def __init__(self, coordinator, client, zone_id):
        super().__init__(coordinator)
        self.client = client
        self.zone_id = zone_id
        self._attr_unique_id = f"{client.ip}_zone_{zone_id}_damper"

    @property
    def name(self):
        return f"{self.coordinator.data['zones'][self.zone_id]['name']} Damper"

    @property
    def native_value(self):
        return self.coordinator.data["zones"][self.zone_id]["userPercentSetting"]

    async def async_set_native_value(self, value: float):
        await self.client.set_zone_data(self.zone_id, "userPercentSetting", str(int(value)))
        await self.coordinator.async_request_refresh()
