from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.myair3.const import CONF_IP, CONF_PASSWORD, DOMAIN

from .conftest import IP, MAC


async def _start(hass, ip=IP, password="password"):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP: ip, CONF_PASSWORD: password}
    )


async def test_creates_entry_keyed_by_mac(hass, controller):
    result = await _start(hass)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "MYAIR3"
    assert result["result"].unique_id == MAC


async def test_wrong_password(hass, controller):
    result = await _start(hass, password="nope")
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect(hass, aioclient_mock):
    import asyncio
    import re
    aioclient_mock.get(re.compile(".*"), exc=asyncio.TimeoutError)
    result = await _start(hass)
    assert result["errors"] == {"base": "cannot_connect"}


async def test_same_controller_twice_updates_ip(hass, controller, entry):
    entry.add_to_hass(hass)
    result = await _start(hass, ip="192.168.1.250")
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_IP] == "192.168.1.250"
