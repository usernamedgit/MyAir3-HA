import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MyAir3Client, MyAir3Error
from .const import DOMAIN, UPDATE_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)

type MyAir3ConfigEntry = ConfigEntry["MyAir3Coordinator"]


class MyAir3Coordinator(DataUpdateCoordinator[dict]):
    config_entry: MyAir3ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: MyAir3ConfigEntry, client: MyAir3Client):
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.client = client
        # Zones whose latest poll failed. Their last good data is kept, but their entities
        # report unavailable until the zone answers again.
        self.failed_zones: set[int] = set()

    async def _async_update_data(self) -> dict:
        try:
            system = await self.client.get_system_data()
        except MyAir3Error as e:
            raise UpdateFailed(f"Error communicating with HVAC system: {e}") from e

        previous = self.data["zones"] if self.data else {}
        zones: dict[int, dict] = {}
        failed: set[int] = set()
        for zone_id in range(1, system["number_of_zones"] + 1):
            try:
                zones[zone_id] = await self.client.get_zone_data(zone_id)
            except MyAir3Error as e:
                if zone_id not in self.failed_zones:
                    _LOGGER.warning("Could not fetch zone %s: %s", zone_id, e)
                failed.add(zone_id)
                if zone_id in previous:
                    zones[zone_id] = previous[zone_id]

        for zone_id in self.failed_zones - failed:
            _LOGGER.info("Zone %s is responding again", zone_id)
        self.failed_zones = failed
        return {"system": system, "zones": zones}
