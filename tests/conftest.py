"""Test fixtures: a fake MyAir3 controller behind Home Assistant's mocked aiohttp session."""

import re
from urllib.parse import parse_qs

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMockResponse,
)

from custom_components.myair3.const import CONF_IP, CONF_PASSWORD, DOMAIN

MAC = "001ec0123456"
IP = "192.168.1.100"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


class FakeController:
    def __init__(self):
        self.password = "password"
        self.authenticated = True
        self.reject_login = False
        self.failing_zones: set[int] = set()
        self.requests: list[tuple[str, dict]] = []
        self.system = {
            "airconOnOff": "0", "fanSpeed": "1", "mode": "1", "unitControlTempsSetting": "4",
            "centralActualTemp": "29.8", "centralDesiredTemp": "23.0", "airConErrorCode": "",
            "numberOfZones": "4", "maxUserTemp": "32.0", "minUserTemp": "16.0",
        }
        self.zones = {
            1: {"name": "KIT + FAMILY", "setting": "0", "userPercentSetting": "100", "maxDamper": "100",
                "minDamper": "0", "actualTemp": "28.7", "desiredTemp": "23.0", "RFstrength": "55",
                "hasLowBatt": "0", "hasMotorError": "0", "hasClimateControl": "1"},
            2: {"name": "HALL", "setting": "1", "userPercentSetting": "50", "maxDamper": "100",
                "minDamper": "10", "actualTemp": "0.0", "desiredTemp": "23.0", "RFstrength": "0",
                "hasLowBatt": "0", "hasMotorError": "0", "hasClimateControl": "0"},
            3: {"name": "MASTER", "setting": "1", "userPercentSetting": "100", "maxDamper": "100",
                "minDamper": "0", "actualTemp": "", "desiredTemp": "21.0", "RFstrength": "40",
                "hasLowBatt": "1", "hasMotorError": "0", "hasClimateControl": "1"},
            4: {"name": "STUDY", "setting": "0", "userPercentSetting": "30", "maxDamper": "100",
                "minDamper": "0", "actualTemp": "", "desiredTemp": "23.0", "RFstrength": "0",
                "hasLowBatt": "0", "hasMotorError": "1", "hasClimateControl": "0"},
        }

    def writes(self) -> list[tuple[str, dict]]:
        return [r for r in self.requests if r[0].startswith("set")]

    def _xml(self, request: str, body: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" ?><iZS10.3>'
            f"<request>{request}</request><mac>{MAC}</mac>"
            f"<authenticated>{int(self.authenticated)}</authenticated>{body}</iZS10.3>"
        )

    async def handle(self, method, url, data):
        path = url.path.lstrip("/")
        q = {k: v[0] for k, v in parse_qs(url.query_string).items()}
        self.requests.append((path, dict(q)))
        if path == "login":
            self.authenticated = not self.reject_login and q.get("password") == self.password
            return AiohttpClientMockResponse(method, url, text=self._xml("login", ""))
        if not self.authenticated:
            return AiohttpClientMockResponse(method, url, text=self._xml(path, ""))
        if path == "getSystemData":
            unit = "".join(f"<{k}>{v}</{k}>" for k, v in self.system.items())
            body = (f"<system><name>MYAIR3</name><MyAppRev>7.4</MyAppRev><unitcontrol>{unit}</unitcontrol>"
                    "<zs103TechSettings><numberofConstantZones>1</numberofConstantZones>"
                    "<zsConstantZone1>2</zsConstantZone1><zsConstantZone2>0</zsConstantZone2>"
                    "<zsConstantZone3>0</zsConstantZone3></zs103TechSettings></system>")
            return AiohttpClientMockResponse(method, url, text=self._xml(path, body))
        if path == "getZoneData":
            n = int(q["zone"])
            if n in self.failing_zones:
                return AiohttpClientMockResponse(method, url, status=500, text="")
            zone = "".join(f"<{k}>{v}</{k}>" for k, v in self.zones[n].items())
            return AiohttpClientMockResponse(method, url, text=self._xml(path, f"<zone{n}>{zone}</zone{n}>"))
        if path == "setSystemData":
            self.system.update(q)
            return AiohttpClientMockResponse(method, url, text=self._xml(path, ""))
        if path == "setZoneData":
            zone = self.zones[int(q.pop("zone"))]
            if "zoneSetting" in q:
                zone["setting"] = q.pop("zoneSetting")
            zone.update(q)
            return AiohttpClientMockResponse(method, url, text=self._xml(path, ""))
        raise AssertionError(f"unexpected request {path}")


@pytest.fixture
def controller(aioclient_mock) -> FakeController:
    fake = FakeController()
    aioclient_mock.get(re.compile(r".*"), side_effect=fake.handle)
    return fake


@pytest.fixture
def entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN, unique_id=MAC, title="MYAIR3",
        data={CONF_IP: IP, CONF_PASSWORD: "password"},
    )


@pytest.fixture
async def setup(hass, controller, entry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
