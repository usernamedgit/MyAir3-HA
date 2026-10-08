import asyncio
import logging
import xml.etree.ElementTree as ET

import aiohttp

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10


class MyAir3Error(Exception):
    pass


class MyAir3AuthError(MyAir3Error):
    pass


class MyAir3ConnectionError(MyAir3Error):
    pass


def _text(element: ET.Element | None, path: str, default: str = "") -> str:
    if element is None:
        return default
    found = element.find(path)
    if found is None or found.text is None:
        return default
    return found.text.strip()


def _float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _int(value: str, default: int = 0) -> int:
    try:
        return int(float(value))
    except ValueError:
        return default


class MyAir3Client:
    def __init__(self, ip: str, password: str, session: aiohttp.ClientSession):
        self.ip = ip
        self.password = password
        self.session = session
        # The controller is a small embedded device; never send it two requests at once.
        self._lock = asyncio.Lock()

    async def _get(self, path: str, params: dict[str, str] | None = None) -> tuple[int, str]:
        # Never log params: the login request carries the password.
        try:
            async with self.session.get(
                f"http://{self.ip}/{path}",
                params=params,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as response:
                return response.status, await response.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise MyAir3ConnectionError(f"Failed to connect to HVAC system at {self.ip}: {e!r}") from e

    async def _login(self) -> bool:
        status, content = await self._get("login", {"password": self.password})
        if status >= 400:
            raise MyAir3ConnectionError(f"Login request failed with HTTP {status}")
        root = self._parse(content)
        auth = _text(root, "authenticated", None)
        if auth is None:
            raise MyAir3ConnectionError("Authentication response missing 'authenticated' element")
        return auth == "1"

    @staticmethod
    def _parse(content: str) -> ET.Element:
        try:
            return ET.fromstring(content)
        except ET.ParseError as e:
            raise MyAir3ConnectionError(f"Invalid XML response from HVAC system: {e}") from e

    @staticmethod
    def _needs_auth(status: int, content: str) -> bool:
        return status in (401, 403) or "<authenticated>0</authenticated>" in content

    async def _request(self, path: str, params: dict[str, str] | None = None) -> ET.Element:
        async with self._lock:
            status, content = await self._get(path, params)
            if self._needs_auth(status, content):
                _LOGGER.debug("Session expired or unauthenticated, logging in")
                if not await self._login():
                    raise MyAir3AuthError("Authentication failed")
                status, content = await self._get(path, params)
                if self._needs_auth(status, content):
                    raise MyAir3AuthError("Controller still reports unauthenticated after login")
            if status >= 400:
                raise MyAir3ConnectionError(f"{path} failed with HTTP {status}")
            return self._parse(content)

    async def authenticate(self) -> bool:
        async with self._lock:
            return await self._login()

    async def get_system_data(self) -> dict:
        root = await self._request("getSystemData")
        unit = root.find("system/unitcontrol")
        on_off = _text(unit, "airconOnOff", None)
        if on_off is None:
            raise MyAir3ConnectionError("Could not find valid 'airconOnOff' element in response")
        tech = root.find("system/zs103TechSettings")
        constant_zones = {
            _int(_text(tech, f"zsConstantZone{i}", "0")) for i in (1, 2, 3)
        } - {0}
        return {
            "mac": _text(root, "mac"),
            "name": _text(root, "system/name") or "MyAir3",
            "firmware": _text(root, "system/MyAppRev") or None,
            "state": "ON" if on_off == "1" else "OFF",
            "mode": _text(unit, "mode", None),
            "fan_speed": _text(unit, "fanSpeed", None),
            "actual_temp": _float(_text(unit, "centralActualTemp")),
            "desired_temp": _float(_text(unit, "centralDesiredTemp")),
            "min_temp": _float(_text(unit, "minUserTemp")),
            "max_temp": _float(_text(unit, "maxUserTemp")),
            "error_code": _text(unit, "airConErrorCode"),
            "number_of_zones": _int(_text(unit, "numberOfZones", "0")),
            "constant_zones": constant_zones,
        }

    async def get_zone_data(self, zone_number: int) -> dict:
        root = await self._request("getZoneData", {"zone": str(zone_number)})
        zone = root.find(f"zone{zone_number}")
        if zone is None:
            raise MyAir3ConnectionError(f"Could not find zone{zone_number} element in response")

        actual = _float(_text(zone, "actualTemp"))
        has_climate = _text(zone, "hasClimateControl", None)
        if has_climate is None:
            # Older firmware may not report it; fall back to whether a temperature is reported.
            has_climate_control = actual is not None and actual != 0.0
        else:
            has_climate_control = has_climate == "1"

        return {
            "name": _text(zone, "name") or f"Zone {zone_number}",
            "setting": _text(zone, "setting", "0"),
            "has_climate_control": has_climate_control,
            "actual_temp": actual if actual not in (None, 0.0) else None,
            "desired_temp": _float(_text(zone, "desiredTemp")),
            "damper": _int(_text(zone, "userPercentSetting", "0")),
            "min_damper": _int(_text(zone, "minDamper", "0")),
            "max_damper": _int(_text(zone, "maxDamper", "100"), 100),
            "rf_strength": _int(_text(zone, "RFstrength", "0")),
            "low_battery": _text(zone, "hasLowBatt") == "1",
            "motor_error": _text(zone, "hasMotorError") == "1",
        }

    async def set_system_data(self, **values: str) -> None:
        await self._request("setSystemData", values)

    async def set_zone_data(self, zone_number: int, **values: str) -> None:
        await self._request("setZoneData", {"zone": str(zone_number), **values})
