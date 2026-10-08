from datetime import timedelta

import pytest
from homeassistant.components.climate import DOMAIN as CLIMATE
from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.myair3.const import CONF_IP, CONF_PASSWORD, DOMAIN

from .conftest import IP, MAC

SYSTEM = "climate.myair3"
KITCHEN = "climate.myair3_kit_family"
MASTER = "climate.myair3_master"


async def _poll(hass):
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()


async def _call(hass, domain, service, entity_id, **data):
    await hass.services.async_call(domain, service, {"entity_id": entity_id, **data}, blocking=True)
    await hass.async_block_till_done()


async def test_entities_created(hass, setup, controller):
    ids = set(hass.states.async_entity_ids())
    # Sensored zones get a climate entity; damper zones get a switch and a damper number.
    assert {SYSTEM, KITCHEN, MASTER} <= ids
    assert {"switch.myair3_hall", "number.myair3_hall_damper", "switch.myair3_study"} <= ids
    assert "climate.myair3_hall" not in ids
    # Zone count comes from the controller (4), not a hard-coded 6.
    zone_requests = {q["zone"] for p, q in controller.requests if p == "getZoneData"}
    assert zone_requests == {"1", "2", "3", "4"}
    # Master's sensor reported no temperature, but hasClimateControl=1 still makes it a thermostat.
    assert hass.states.get(MASTER).attributes["current_temperature"] is None
    # All entities hang off one device keyed by MAC.
    reg = er.async_get(hass)
    assert reg.async_get(KITCHEN).unique_id == f"{MAC}_zone_1_climate"


async def test_zone_modes_follow_central_unit(hass, setup, controller):
    state = hass.states.get(KITCHEN)
    assert state.state == HVACMode.OFF
    assert state.attributes["hvac_modes"] == [HVACMode.OFF, HVACMode.COOL]

    await _call(hass, CLIMATE, "set_hvac_mode", KITCHEN, hvac_mode=HVACMode.COOL)
    assert controller.writes()[-1] == ("setZoneData", {"zone": "1", "zoneSetting": "1"})
    state = hass.states.get(KITCHEN)
    assert state.state == HVACMode.COOL
    assert state.attributes["hvac_action"] == HVACAction.IDLE  # central unit is off

    # A mode the zone can't have is rejected rather than silently opening the zone.
    with pytest.raises(ServiceValidationError):
        await _call(hass, CLIMATE, "set_hvac_mode", KITCHEN, hvac_mode=HVACMode.HEAT)

    # Switch the central unit to heat: the zone now offers off/heat and shows heating.
    await _call(hass, CLIMATE, "set_hvac_mode", SYSTEM, hvac_mode=HVACMode.HEAT)
    assert controller.system["airconOnOff"] == "1"
    assert controller.system["mode"] == "2"
    await _poll(hass)
    state = hass.states.get(KITCHEN)
    assert state.attributes["hvac_modes"] == [HVACMode.OFF, HVACMode.HEAT]
    assert state.state == HVACMode.HEAT
    assert state.attributes["hvac_action"] == HVACAction.HEATING

    await _call(hass, CLIMATE, "turn_off", KITCHEN)
    assert controller.zones[1]["setting"] == "0"


async def test_central_turn_on_off_and_fan(hass, setup, controller):
    await _call(hass, CLIMATE, "turn_on", SYSTEM)
    assert controller.system["airconOnOff"] == "1"
    assert hass.states.get(SYSTEM).state == HVACMode.COOL
    await _call(hass, CLIMATE, "set_fan_mode", SYSTEM, fan_mode="medium")
    assert controller.system["fanSpeed"] == "2"
    await _poll(hass)  # refreshes after back-to-back commands are debounced
    assert hass.states.get(SYSTEM).attributes["fan_mode"] == "medium"
    await _call(hass, CLIMATE, "turn_off", SYSTEM)
    await _poll(hass)
    assert hass.states.get(SYSTEM).state == HVACMode.OFF


async def test_setpoint_limits_and_whole_degrees(hass, setup, controller):
    attrs = hass.states.get(SYSTEM).attributes
    assert (attrs["min_temp"], attrs["max_temp"], attrs["target_temp_step"]) == (16, 32, 1)
    await _call(hass, CLIMATE, "set_temperature", SYSTEM, temperature=24)
    assert controller.system["centralDesiredTemp"] == "24.0"
    with pytest.raises(ServiceValidationError):
        await _call(hass, CLIMATE, "set_temperature", SYSTEM, temperature=35)

    # Zone setpoint goes with the zone's current open/closed setting, as the app sends it.
    await _call(hass, CLIMATE, "set_temperature", KITCHEN, temperature=22)
    assert controller.writes()[-1] == (
        "setZoneData", {"zone": "1", "desiredTemp": "22.0", "zoneSetting": "0"}
    )
    assert controller.zones[1]["setting"] == "0"


async def test_damper_limits(hass, setup, controller):
    attrs = hass.states.get("number.myair3_hall_damper").attributes
    assert (attrs["min"], attrs["max"], attrs["unit_of_measurement"]) == (10, 100, "%")
    await _call(hass, "number", "set_value", "number.myair3_hall_damper", value=55)
    assert controller.zones[2]["userPercentSetting"] == "55"
    await _call(hass, "switch", "turn_off", "switch.myair3_hall")
    assert controller.zones[2]["setting"] == "0"


async def test_diagnostics(hass, setup, controller):
    assert hass.states.get("binary_sensor.myair3_fault").state == "off"
    assert hass.states.get("binary_sensor.myair3_master_sensor_battery").state == "on"
    assert hass.states.get("binary_sensor.myair3_study_damper_motor").state == "on"
    assert hass.states.get("sensor.myair3_kit_family_sensor_signal").state == "55"
    assert hass.states.get("binary_sensor.myair3_hall_sensor_battery") is None
    controller.system["airConErrorCode"] = "E3"
    await _poll(hass)
    fault = hass.states.get("binary_sensor.myair3_fault")
    assert fault.state == "on" and fault.attributes["error_code"] == "E3"


async def test_temperature_sensors(hass, setup, controller):
    central = hass.states.get("sensor.myair3_controller_temperature")
    assert central.state == "29.8"
    assert central.attributes["friendly_name"] == "MYAIR3 Controller temperature"
    # Renaming kept the unique ID, so existing installs keep their entity ID and history.
    assert er.async_get(hass).async_get(central.entity_id).unique_id == f"{MAC}_temperature"
    assert central.attributes["device_class"] == "temperature"
    assert central.attributes["state_class"] == "measurement"
    assert central.attributes["unit_of_measurement"] == "°C"
    assert hass.states.get("sensor.myair3_kit_family_temperature").state == "28.7"
    # A sensored zone that reports no reading is unknown; damper zones get no sensor.
    assert hass.states.get("sensor.myair3_master_temperature").state == "unknown"
    assert hass.states.get("sensor.myair3_hall_temperature") is None
    controller.zones[1]["actualTemp"] = "25.1"
    await _poll(hass)
    assert hass.states.get("sensor.myair3_kit_family_temperature").state == "25.1"


async def test_failed_zone_poll_marks_only_that_zone_unavailable(hass, setup, controller):
    controller.failing_zones = {1}
    await _poll(hass)
    assert hass.states.get(KITCHEN).state == STATE_UNAVAILABLE
    assert hass.states.get(MASTER).state != STATE_UNAVAILABLE
    controller.failing_zones = set()
    await _poll(hass)
    assert hass.states.get(KITCHEN).state == HVACMode.OFF


async def test_zone_missing_at_startup_is_added_later(hass, controller, entry):
    controller.failing_zones = {3}
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(MASTER) is None
    controller.failing_zones = set()
    await _poll(hass)
    assert hass.states.get(MASTER).state == HVACMode.COOL


async def test_relogin_when_session_expires(hass, setup, controller):
    controller.authenticated = False
    await _call(hass, CLIMATE, "turn_on", SYSTEM)
    assert controller.system["airconOnOff"] == "1"
    assert ("login", {"password": "password"}) in controller.requests


async def test_command_fails_loudly_when_login_fails(hass, setup, controller):
    controller.authenticated = False
    controller.reject_login = True
    with pytest.raises(HomeAssistantError):
        await _call(hass, CLIMATE, "turn_on", SYSTEM)
    assert controller.system["airconOnOff"] == "0"


async def test_password_is_url_encoded(hass, controller):
    controller.password = "p&ss#1"
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    from custom_components.myair3.api import MyAir3Client

    client = MyAir3Client(IP, "p&ss#1", async_get_clientsession(hass))
    assert await client.authenticate()


async def test_legacy_entry_is_migrated_to_mac(hass, controller):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_IP: IP, CONF_PASSWORD: "password"})
    entry.add_to_hass(hass)
    reg = er.async_get(hass)
    old = reg.async_get_or_create(
        CLIMATE, DOMAIN, f"{IP}_zone_1_climate", config_entry=entry, suggested_object_id="kit_family"
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.unique_id == MAC
    migrated = reg.async_get(old.entity_id)
    assert migrated.unique_id == f"{MAC}_zone_1_climate"
    assert hass.states.get(old.entity_id).state == HVACMode.OFF


async def test_unload(hass, setup):
    assert await hass.config_entries.async_unload(setup.entry_id)
    assert setup.state is ConfigEntryState.NOT_LOADED
