import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MyAir3AuthError, MyAir3Client, MyAir3ConnectionError
from .const import CONF_IP, CONF_PASSWORD, DEFAULT_IP, DEFAULT_PASSWORD, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP, default=DEFAULT_IP): str,
        vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
    }
)


class MyAir3ConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            client = MyAir3Client(
                user_input[CONF_IP], user_input[CONF_PASSWORD], async_get_clientsession(self.hass)
            )
            try:
                if not await client.authenticate():
                    raise MyAir3AuthError
                system = await client.get_system_data()
            except MyAir3AuthError:
                errors["base"] = "invalid_auth"
            except MyAir3ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if not system["mac"]:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(system["mac"])
                    # Re-adding a controller that moved to a new IP updates the existing entry.
                    self._abort_if_unique_id_configured(updates={CONF_IP: user_input[CONF_IP]})
                    return self.async_create_entry(title=system["name"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_DATA_SCHEMA, user_input),
            errors=errors,
        )
