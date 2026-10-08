from datetime import timedelta

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

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


async def test_reconfigure_changes_ip_and_password(hass, controller, setup):
    controller.password = "newpass"
    result = await setup.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP: "192.168.1.250", CONF_PASSWORD: "wrong"}
    )
    assert result["errors"] == {"base": "invalid_auth"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP: "192.168.1.250", CONF_PASSWORD: "newpass"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert setup.data == {CONF_IP: "192.168.1.250", CONF_PASSWORD: "newpass"}


async def test_reconfigure_rejects_a_different_controller(hass, controller, setup):
    controller.mac = "001ec0999999"
    result = await setup.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP: "192.168.1.250", CONF_PASSWORD: "password"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert setup.data[CONF_IP] == IP


async def test_rejected_password_starts_reauth(hass, controller, setup):
    controller.password = "newpass"
    controller.authenticated = False
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [f["context"]["source"] for f in flows] == [config_entries.SOURCE_REAUTH]
    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], {CONF_PASSWORD: "newpass"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert setup.data[CONF_PASSWORD] == "newpass"
    await hass.async_block_till_done()
    assert setup.state is ConfigEntryState.LOADED
