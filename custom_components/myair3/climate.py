from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    client = hass.data[DOMAIN][entry.entry_id]["client"]
    entities = []

    # Add the main AC system
    entities.append(MyAir3SystemClimate(coordinator, client))

    # Add any zones with temp sensors
    for zone_id, zone_data in coordinator.data.get("zones", {}).items():
        if zone_data.get("actualTemp") is not None:
            entities.append(MyAir3ZoneClimate(coordinator, client, zone_id))

    async_add_entities(entities)

class MyAir3SystemClimate(CoordinatorEntity, ClimateEntity):
    _attr_has_entity_name = True
    _attr_name = "Central System"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.FAN_ONLY]
    _attr_fan_modes = ["low", "med", "high"]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
    )

    def __init__(self, coordinator, client):
        super().__init__(coordinator)
        self.client = client
        self._attr_unique_id = f"{client.ip}_system_climate"

    @property
    def current_temperature(self):
        return self.coordinator.data["system"]["actual_temp"]

    @property
    def target_temperature(self):
        return self.coordinator.data["system"]["desired_temp"]

    @property
    def hvac_mode(self):
        state = self.coordinator.data["system"]["state"]
        if state == "OFF":
            return HVACMode.OFF
        mode = self.coordinator.data["system"]["mode"]
        if mode == "1":
            return HVACMode.COOL
        elif mode == "2":
            return HVACMode.HEAT
        elif mode == "3":
            return HVACMode.FAN_ONLY
        return HVACMode.AUTO

    @property
    def fan_mode(self):
        speed = self.coordinator.data["system"]["fan_speed"]
        if speed == "1": return "low"
        if speed == "2": return "med"
        if speed == "3": return "high"
        return "auto"

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self.client.set_system_data("centralDesiredTemp", str(temp))
            await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        if hvac_mode == HVACMode.OFF:
            await self.client.set_system_data("airconOnOff", "0")
        else:
            await self.client.set_system_data("airconOnOff", "1")
            mode_map = {HVACMode.COOL: "1", HVACMode.HEAT: "2", HVACMode.FAN_ONLY: "3"}
            if hvac_mode in mode_map:
                await self.client.set_system_data("mode", mode_map[hvac_mode])
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str):
        fan_map = {"low": "1", "med": "2", "high": "3"}
        if fan_mode in fan_map:
            await self.client.set_system_data("fanSpeed", fan_map[fan_mode])
            await self.coordinator.async_request_refresh()

class MyAir3ZoneClimate(CoordinatorEntity, ClimateEntity):
    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, coordinator, client, zone_id):
        super().__init__(coordinator)
        self.client = client
        self.zone_id = zone_id
        self._attr_unique_id = f"{client.ip}_zone_{zone_id}_climate"

    @property
    def name(self):
        return self.coordinator.data["zones"][self.zone_id]["name"]

    @property
    def current_temperature(self):
        return self.coordinator.data["zones"][self.zone_id]["actualTemp"]

    @property
    def target_temperature(self):
        return self.coordinator.data["zones"][self.zone_id]["desiredTemp"]

    @property
    def hvac_modes(self):
        return [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.FAN_ONLY, HVACMode.AUTO]

    @property
    def hvac_mode(self):
        setting = self.coordinator.data["zones"][self.zone_id]["setting"]
        if setting == "0":
            return HVACMode.OFF
            
        main_state = self.coordinator.data["system"]["state"]
        if main_state == "OFF":
            return HVACMode.FAN_ONLY
            
        mode = self.coordinator.data["system"]["mode"]
        if mode == "1": return HVACMode.COOL
        elif mode == "2": return HVACMode.HEAT
        elif mode == "3": return HVACMode.FAN_ONLY
        return HVACMode.AUTO

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self.client.set_zone_data(self.zone_id, "desiredTemp", str(temp))
            await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        val = "0" if hvac_mode == HVACMode.OFF else "1"
        await self.client.set_zone_data(self.zone_id, "zoneSetting", val)
        await self.coordinator.async_request_refresh()
