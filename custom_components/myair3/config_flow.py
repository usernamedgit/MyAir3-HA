import logging
from collections.abc import Mapping
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
STEP_RECONFIGURE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP): str,
        vol.Required(CONF_PASSWORD): str,
    }
)
STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class MyAir3ConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _async_validate(self, ip: str, password: str, errors: dict[str, str]) -> dict | None:
        """Log in and read the controller. Returns its system data, or None with errors filled in."""
        client = MyAir3Client(ip, password, async_get_clientsession(self.hass))
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
            if system["mac"]:
                return system
            errors["base"] = "cannot_connect"
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            system = await self._async_validate(user_input[CONF_IP], user_input[CONF_PASSWORD], errors)
            if system is not None:
                await self.async_set_unique_id(system["mac"])
                # Re-adding a controller that moved to a new IP updates the existing entry.
                self._abort_if_unique_id_configured(updates={CONF_IP: user_input[CONF_IP]})
                return self.async_create_entry(title=system["name"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_DATA_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the IP address or password of an existing entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            system = await self._async_validate(user_input[CONF_IP], user_input[CONF_PASSWORD], errors)
            if system is not None:
                await self.async_set_unique_id(system["mac"])
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(entry, data_updates=user_input)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_RECONFIGURE_DATA_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new password after the controller rejected the stored one."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            system = await self._async_validate(entry.data[CONF_IP], user_input[CONF_PASSWORD], errors)
            if system is not None:
                await self.async_set_unique_id(system["mac"])
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(entry, data_updates=user_input)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            description_placeholders={"ip_address": entry.data[CONF_IP]},
            errors=errors,
        )
