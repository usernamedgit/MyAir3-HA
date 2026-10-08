import logging
import re

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MyAir3Client
from .const import CONF_IP, CONF_PASSWORD
from .coordinator import MyAir3ConfigEntry, MyAir3Coordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Entity unique IDs from before 1.1.0 were prefixed with the controller's IP address.
_LEGACY_UNIQUE_ID = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}_(.+)$")


async def async_setup_entry(hass: HomeAssistant, entry: MyAir3ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    client = MyAir3Client(entry.data[CONF_IP], entry.data[CONF_PASSWORD], session)
    coordinator = MyAir3Coordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    mac = coordinator.data["system"]["mac"]
    if entry.unique_id is None and mac:
        # Entries created before 1.1.0 had no unique ID; adopt the controller's MAC and
        # carry the existing entities over so their history and entity IDs are kept.
        hass.config_entries.async_update_entry(entry, unique_id=mac)
        await _async_migrate_entity_ids(hass, entry, mac)

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_migrate_entity_ids(hass: HomeAssistant, entry: MyAir3ConfigEntry, mac: str) -> None:
    @callback
    def migrate(entity_entry: er.RegistryEntry) -> dict | None:
        match = _LEGACY_UNIQUE_ID.match(entity_entry.unique_id)
        if match is None:
            return None
        new_id = f"{mac}_{match.group(1)}"
        _LOGGER.debug("Migrating unique ID %s to %s", entity_entry.unique_id, new_id)
        return {"new_unique_id": new_id}

    await er.async_migrate_entries(hass, entry.entry_id, migrate)


async def async_unload_entry(hass: HomeAssistant, entry: MyAir3ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
