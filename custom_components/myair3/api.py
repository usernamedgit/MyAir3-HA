import aiohttp
import asyncio
import xml.etree.ElementTree as ET
import logging

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10

class MyAir3AuthError(Exception):
    pass

class MyAir3ConnectionError(Exception):
    pass

class MyAir3Client:
    def __init__(self, ip: str, password: str, session: aiohttp.ClientSession):
        self.ip = ip
        self.password = password
        self.session = session

    async def _make_request(self, url: str, max_retries: int = 1) -> str:
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as response:
                content = await response.text()
                
                if "<authenticated>0</authenticated>" in content and max_retries > 0:
                    _LOGGER.debug("Session expired or unauthenticated. Logging in...")
                    if await self.authenticate():
                        return await self._make_request(url, max_retries - 1)
                    else:
                        raise MyAir3AuthError("Authentication failed.")
                        
                if response.status in (401, 403) and max_retries > 0:
                    _LOGGER.debug("Authentication required. Logging in...")
                    if await self.authenticate():
                        return await self._make_request(url, max_retries - 1)
                    else:
                        raise MyAir3AuthError("Authentication failed.")
                
                response.raise_for_status()
                return content
                
        except aiohttp.ClientError as e:
            raise MyAir3ConnectionError(f"Failed to connect to HVAC system at {self.ip}: {e}")

    async def authenticate(self) -> bool:
        url = f"http://{self.ip}/login?password={self.password}"
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as response:
                response.raise_for_status()
                xml_content = await response.text()
                
            root = ET.fromstring(xml_content)
            auth_element = root.find('.//authenticated')
            if auth_element is None or auth_element.text is None:
                raise MyAir3ConnectionError("Authentication response missing 'authenticated' element")
                
            return auth_element.text == "1"
            
        except aiohttp.ClientError as e:
            raise MyAir3ConnectionError(f"Failed to connect to HVAC system at {self.ip}: {e}")
        except ET.ParseError as e:
            raise MyAir3ConnectionError(f"Invalid XML response from HVAC system: {e}")

    async def get_system_data(self) -> dict:
        url = f"http://{self.ip}/getSystemData"
        xml_content = await self._make_request(url)
        
        try:
            root = ET.fromstring(xml_content)
            
            aircon_element = root.find('.//unitcontrol/airconOnOff')
            if aircon_element is None or aircon_element.text is None:
                raise MyAir3ConnectionError(f"Could not find valid 'airconOnOff' element in response.")
                
            status_value = aircon_element.text.strip()
            state = "ON" if status_value == "1" else "OFF"
            
            central_actual = root.find('.//unitcontrol/centralActualTemp')
            actual_temp = central_actual.text.strip() if central_actual is not None and central_actual.text is not None else "0.0"
            
            central_desired = root.find('.//unitcontrol/centralDesiredTemp')
            desired_temp = central_desired.text.strip() if central_desired is not None and central_desired.text is not None else "0.0"
            
            fan_element = root.find('.//unitcontrol/fanSpeed')
            fan_speed = fan_element.text.strip() if fan_element is not None and fan_element.text is not None else "1"
            
            mode_element = root.find('.//unitcontrol/mode')
            mode = mode_element.text.strip() if mode_element is not None and mode_element.text is not None else "1"
            
            return {
                "state": state,
                "actual_temp": float(actual_temp) if actual_temp else 0.0,
                "desired_temp": float(desired_temp) if desired_temp else 0.0,
                "fan_speed": fan_speed,
                "mode": mode
            }
                
        except ET.ParseError as e:
            raise MyAir3ConnectionError(f"Invalid XML response from HVAC system: {e}")

    async def get_zone_data(self, zone_number: int) -> dict:
        url = f"http://{self.ip}/getZoneData?zone={zone_number}"
        xml_content = await self._make_request(url)
        
        try:
            root = ET.fromstring(xml_content)
            zone_element = root.find(f'.//zone{zone_number}')
            if zone_element is None:
                raise MyAir3ConnectionError(f"Could not find zone{zone_number} element in response")
                
            result = {}
            
            name_elem = zone_element.find('name')
            result['name'] = name_elem.text.strip() if name_elem is not None and name_elem.text is not None else f'Zone {zone_number}'
            
            setting_elem = zone_element.find('setting')
            result['setting'] = setting_elem.text.strip() if setting_elem is not None and setting_elem.text is not None else '0'
            
            actual_temp_elem = zone_element.find('actualTemp')
            actual_temp_str = actual_temp_elem.text.strip() if actual_temp_elem is not None and actual_temp_elem.text else ''
            result['actualTemp'] = float(actual_temp_str) if actual_temp_str and actual_temp_str != "0.0" else None
            
            desired_temp_elem = zone_element.find('desiredTemp')
            desired_temp_str = desired_temp_elem.text.strip() if desired_temp_elem is not None and desired_temp_elem.text is not None else ''
            result['desiredTemp'] = float(desired_temp_str) if desired_temp_str else None
            
            damper_elem = zone_element.find('userPercentSetting')
            result['userPercentSetting'] = int(damper_elem.text.strip()) if damper_elem is not None and damper_elem.text is not None else 0
            
            return result
                
        except ET.ParseError as e:
            raise MyAir3ConnectionError(f"Invalid XML response from HVAC system: {e}")

    async def set_system_data(self, param: str, value: str):
        url = f"http://{self.ip}/setSystemData?{param}={value}"
        await self._make_request(url)

    async def set_zone_data(self, zone_number: int, param: str, value: str):
        url = f"http://{self.ip}/setZoneData?zone={zone_number}&{param}={value}"
        await self._make_request(url)
