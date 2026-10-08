from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    FAN_SPEED_HIGH,
    FAN_SPEED_LOW,
    FAN_SPEED_MEDIUM,
    MODE_COOL,
    MODE_FAN,
    MODE_HEAT,
)
from .coordinator import MyAir3ConfigEntry, MyAir3Coordinator
from .entity import MyAir3Entity, MyAir3ZoneEntity, handle_errors, setup_zone_entities

MODE_TO_HVAC = {MODE_COOL: HVACMode.COOL, MODE_HEAT: HVACMode.HEAT, MODE_FAN: HVACMode.FAN_ONLY}
HVAC_TO_MODE = {hvac: mode for mode, hvac in MODE_TO_HVAC.items()}
HVAC_TO_ACTION = {
    HVACMode.COOL: HVACAction.COOLING,
    HVACMode.HEAT: HVACAction.HEATING,
    HVACMode.FAN_ONLY: HVACAction.FAN,
}
SPEED_TO_FAN = {FAN_SPEED_LOW: FAN_LOW, FAN_SPEED_MEDIUM: FAN_MEDIUM, FAN_SPEED_HIGH: FAN_HIGH}
FAN_TO_SPEED = {fan: speed for speed, fan in SPEED_TO_FAN.items()}

DEFAULT_MIN_TEMP = 16.0
DEFAULT_MAX_TEMP = 32.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyAir3ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([MyAir3SystemClimate(entry.runtime_data)])

    def zone_entities(coordinator: MyAir3Coordinator, zone_id: int, zone: dict):
        if zone["has_climate_control"]:
            yield MyAir3ZoneClimate(coordinator, zone_id)

    setup_zone_entities(entry, async_add_entities, zone_entities)


class _MyAir3ClimateBase(ClimateEntity):
    """Shared temperature settings; the controller works in whole degrees."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_precision = 0.1

    @property
    def min_temp(self) -> float:
        return self.system["min_temp"] or DEFAULT_MIN_TEMP

    @property
    def max_temp(self) -> float:
        return self.system["max_temp"] or DEFAULT_MAX_TEMP

    @property
    def central_hvac_mode(self) -> HVACMode | None:
        """The mode the central unit is set to, whether or not it is running."""
        return MODE_TO_HVAC.get(self.system["mode"])

    def _clamp(self, temperature: float) -> str:
        temperature = min(max(round(temperature), self.min_temp), self.max_temp)
        return f"{temperature:.1f}"


class MyAir3SystemClimate(MyAir3Entity, _MyAir3ClimateBase):
    _attr_name = None  # the device itself
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.FAN_ONLY]
    _attr_fan_modes = [FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: MyAir3Coordinator):
        super().__init__(coordinator, "system_climate")

    @property
    def is_on(self) -> bool:
        return self.system["state"] == "ON"

    @property
    def current_temperature(self) -> float | None:
        return self.system["actual_temp"]

    @property
    def target_temperature(self) -> float | None:
        return self.system["desired_temp"]

    @property
    def hvac_mode(self) -> HVACMode | None:
        return self.central_hvac_mode if self.is_on else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        if not self.is_on:
            return HVACAction.OFF
        return HVAC_TO_ACTION.get(self.central_hvac_mode)

    @property
    def fan_mode(self) -> str | None:
        return SPEED_TO_FAN.get(self.system["fan_speed"])

    @handle_errors
    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            await self._set_hvac_mode(hvac_mode)
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.client.set_system_data(centralDesiredTemp=self._clamp(temperature))

    @handle_errors
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self._set_hvac_mode(hvac_mode)

    async def _set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.client.set_system_data(airconOnOff="0")
            return
        if not self.is_on:
            await self.client.set_system_data(airconOnOff="1")
        if hvac_mode != self.central_hvac_mode:
            await self.client.set_system_data(mode=HVAC_TO_MODE[hvac_mode])

    @handle_errors
    async def async_turn_on(self) -> None:
        await self.client.set_system_data(airconOnOff="1")

    @handle_errors
    async def async_turn_off(self) -> None:
        await self.client.set_system_data(airconOnOff="0")

    @handle_errors
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        await self.client.set_system_data(fanSpeed=FAN_TO_SPEED[fan_mode])


class MyAir3ZoneClimate(MyAir3ZoneEntity, _MyAir3ClimateBase):
    """A temperature-controlled zone.

    A zone can only be opened or closed; it always runs in the central unit's mode.
    So it offers just two modes: off, and whatever the central unit is set to.
    """

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: MyAir3Coordinator, zone_id: int):
        super().__init__(coordinator, zone_id, "climate")

    @property
    def name(self) -> str:
        return self.zone_name

    @property
    def is_open(self) -> bool:
        return self.zone["setting"] == "1"

    @property
    def hvac_modes(self) -> list[HVACMode]:
        if (mode := self.central_hvac_mode) is None:
            return [HVACMode.OFF]
        return [HVACMode.OFF, mode]

    @property
    def hvac_mode(self) -> HVACMode | None:
        return self.central_hvac_mode if self.is_open else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        if not self.is_open:
            return HVACAction.OFF
        if self.system["state"] != "ON":
            # Zone is open, but the central unit isn't running.
            return HVACAction.IDLE
        return HVAC_TO_ACTION.get(self.central_hvac_mode)

    @property
    def current_temperature(self) -> float | None:
        return self.zone["actual_temp"]

    @property
    def target_temperature(self) -> float | None:
        return self.zone["desired_temp"]

    @handle_errors
    async def async_set_temperature(self, **kwargs: Any) -> None:
        setting = self.zone["setting"]
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            setting = "0" if hvac_mode == HVACMode.OFF else "1"
        params = {}
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            params["desiredTemp"] = self._clamp(temperature)
        # The MyAir app always sends zoneSetting along with the setpoint, so do the same,
        # keeping the zone open or closed as it was.
        params["zoneSetting"] = setting
        await self.client.set_zone_data(self.zone_id, **params)

    @handle_errors
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self.client.set_zone_data(
            self.zone_id, zoneSetting="0" if hvac_mode == HVACMode.OFF else "1"
        )

    @handle_errors
    async def async_turn_on(self) -> None:
        await self.client.set_zone_data(self.zone_id, zoneSetting="1")

    @handle_errors
    async def async_turn_off(self) -> None:
        await self.client.set_zone_data(self.zone_id, zoneSetting="0")
