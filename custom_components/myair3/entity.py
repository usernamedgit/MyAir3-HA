from collections.abc import Awaitable, Callable, Iterable
from functools import wraps
from typing import Concatenate

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import MyAir3Error
from .const import DOMAIN, MANUFACTURER
from .coordinator import MyAir3ConfigEntry, MyAir3Coordinator


def handle_errors[E: "MyAir3Entity", **P](
    func: Callable[Concatenate[E, P], Awaitable[None]],
) -> Callable[Concatenate[E, P], Awaitable[None]]:
    """Turn controller errors into HomeAssistantError and refresh state after a command."""

    @wraps(func)
    async def wrapper(self: E, *args: P.args, **kwargs: P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except MyAir3Error as e:
            raise HomeAssistantError(f"Command to the HVAC system failed: {e}") from e
        finally:
            await self.coordinator.async_request_refresh()

    return wrapper


class MyAir3Entity(CoordinatorEntity[MyAir3Coordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: MyAir3Coordinator, key: str):
        super().__init__(coordinator)
        mac = coordinator.config_entry.unique_id or coordinator.config_entry.entry_id
        self.client = coordinator.client
        self._attr_unique_id = f"{mac}_{key}"
        system = coordinator.data["system"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            connections={(CONNECTION_NETWORK_MAC, format_mac(mac))},
            manufacturer=MANUFACTURER,
            model="MyAir3",
            name=system["name"],
            sw_version=system["firmware"],
            configuration_url=f"http://{coordinator.client.ip}",
        )

    @property
    def system(self) -> dict:
        return self.coordinator.data["system"]


class MyAir3ZoneEntity(MyAir3Entity):
    def __init__(self, coordinator: MyAir3Coordinator, zone_id: int, key: str):
        super().__init__(coordinator, f"zone_{zone_id}_{key}")
        self.zone_id = zone_id

    @property
    def zone(self) -> dict:
        return self.coordinator.data["zones"][self.zone_id]

    @property
    def zone_name(self) -> str:
        return self.zone["name"]

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.zone_id in self.coordinator.data["zones"]
            and self.zone_id not in self.coordinator.failed_zones
        )


def setup_zone_entities(
    entry: MyAir3ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    factory: Callable[[MyAir3Coordinator, int, dict], Iterable[Entity]],
) -> None:
    """Add entities for each zone, including zones that first answer after startup."""
    coordinator = entry.runtime_data
    added: set[int] = set()

    @callback
    def add_new_zones() -> None:
        new: list[Entity] = []
        for zone_id, zone in coordinator.data["zones"].items():
            if zone_id not in added:
                added.add(zone_id)
                new.extend(factory(coordinator, zone_id, zone))
        if new:
            async_add_entities(new)

    add_new_zones()
    entry.async_on_unload(coordinator.async_add_listener(add_new_zones))

