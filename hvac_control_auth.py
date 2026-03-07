#!/usr/bin/env python3
"""
HVAC Control Script for myAir/iZS10.3 System

This script provides command-line control of a myAir HVAC system,
allowing users to turn the AC on/off, change modes, set fan speed,
manage individual zones, and check the current system status.

Usage:
    python hvac_control_auth.py --on                   # Turn AC on
    python hvac_control_auth.py --off                  # Turn AC off
    python hvac_control_auth.py --mode heat            # Set AC to heat mode (cool, heat, fan)
    python hvac_control_auth.py --fan high             # Set fan speed (low, med, high)
    python hvac_control_auth.py --zone                 # Open interactive zone control
    python hvac_control_auth.py --status               # Check current status
    python hvac_control_auth.py --ip 192.168.1.X ...   # Specify a custom IP (default: 192.168.1.209)

The script uses lazy authentication, only sending login requests
when the HVAC system indicates the session has expired.
"""

import argparse
import sys
import urllib.request
import urllib.error
from xml.etree import ElementTree


# Default password for the HVAC system (as specified in myAir_commands.txt)
DEFAULT_PASSWORD = "password"

# HTTP request timeout in seconds
REQUEST_TIMEOUT = 10


def authenticate(ip: str, password: str = DEFAULT_PASSWORD) -> bool:
    """
    Authenticate with the HVAC system.
    
    Sends a GET request to {ip}/login?password={password} and checks if
    authentication was successful by parsing the XML response.
    
    Args:
        ip: The IP address of the HVAC system
        password: The password for authentication
        
    Returns:
        True if authentication was successful, False otherwise
        
    Raises:
        RuntimeError: If network request fails or response is invalid
    """
    url = f"http://{ip}/login?password={password}"
    
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT) as response:
            xml_content = response.read().decode('utf-8')
            
        # Parse XML and check authentication status
        root = ElementTree.fromstring(xml_content)
        
        # Find the authenticated element in the XML
        auth_element = root.find('.//authenticated')
        if auth_element is None:
            raise RuntimeError("Authentication response missing 'authenticated' element")
            
        return auth_element.text == "1"
        
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HVAC system returned HTTP error {e.code} during authentication")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to connect to HVAC system at {ip}: {e.reason}")
    except ElementTree.ParseError as e:
        raise RuntimeError(f"Invalid XML response from HVAC system: {e}")


def _make_request(url: str, ip: str, password: str, max_retries: int = 1) -> str:
    """
    Helper function to make an HTTP request to the HVAC system with lazy authentication.
    
    Tries to make the request first. If it encounters a 401/403 error, OR if the 
    returned XML indicates <authenticated>0</authenticated>, it calls authenticate()
    and then retries the request.
    
    Args:
        url: The full URL to request
        ip: The IP address of the HVAC system (needed for authentication)
        password: The password for authentication
        max_retries: Number of times to retry after authenticating
        
    Returns:
        The decoded string content of the response
        
    Raises:
        RuntimeError: If the request fails, authentication fails, or retries are exhausted
    """
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT) as response:
            content = response.read().decode('utf-8')
            
            # The HVAC system returns HTTP 200 even when not authenticated, 
            # but includes <authenticated>0</authenticated> in the XML.
            if "<authenticated>0</authenticated>" in content and max_retries > 0:
                print("Session expired or unauthenticated. Logging in...")
                if authenticate(ip, password):
                    return _make_request(url, ip, password, max_retries - 1)
                else:
                    raise RuntimeError("Authentication failed.")
                    
            return content
            
    except urllib.error.HTTPError as e:
        if e.code in (401, 403) and max_retries > 0:
            print("Authentication required. Logging in...")
            if authenticate(ip, password):
                return _make_request(url, ip, password, max_retries - 1)
            else:
                raise RuntimeError("Authentication failed.")
        else:
            raise RuntimeError(f"HVAC system returned HTTP error {e.code} for URL {url}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to connect to HVAC system at {ip}: {e.reason}")
def turn_on(ip: str, password: str = DEFAULT_PASSWORD) -> bool:
    """
    Turn the AC on.
    
    Checks the current status with lazy authentication,
    and then sends a command to set airconOnOff=1 if it's not already on.
    
    Args:
        ip: The IP address of the HVAC system
        password: The password for authentication
        
    Returns:
        True if AC was successfully turned on or was already on
        
    Raises:
        RuntimeError: If authentication fails or network request fails
    """
    # Check current status
    current_status = get_status(ip, password)
    if current_status["state"] == "ON":
        print("AC is already ON. No command sent.")
        return True
    
    url = f"http://{ip}/setSystemData?airconOnOff=1"
    
    try:
        xml_content = _make_request(url, ip, password)
        
        # Parse XML to verify the command was accepted
        root = ElementTree.fromstring(xml_content)
        request_element = root.find('.//request')
        
        if request_element is not None and request_element.text == "setSystemData":
            print("AC turned ON successfully.")
            return True
            
        print("Command sent to HVAC system (response format unexpected but likely successful).")
        return True
        
    except ElementTree.ParseError as e:
        raise RuntimeError(f"Invalid XML response from HVAC system: {e}")


def turn_off(ip: str, password: str = DEFAULT_PASSWORD) -> bool:
    """
    Turn the AC off.
    
    Checks the current status with lazy authentication,
    and then sends a command to set airconOnOff=0 if it's not already off.
    
    Args:
        ip: The IP address of the HVAC system
        password: The password for authentication
        
    Returns:
        True if AC was successfully turned off or was already off
        
    Raises:
        RuntimeError: If authentication fails or network request fails
    """
    # Check current status
    current_status = get_status(ip, password)
    if current_status["state"] == "OFF":
        print("AC is already OFF. No command sent.")
        return True
    
    url = f"http://{ip}/setSystemData?airconOnOff=0"
    
    try:
        xml_content = _make_request(url, ip, password)
            
        # Parse XML to verify the command was accepted
        root = ElementTree.fromstring(xml_content)
        request_element = root.find('.//request')
        
        if request_element is not None and request_element.text == "setSystemData":
            print("AC turned OFF successfully.")
            return True
            
        print("Command sent to HVAC system (response format unexpected but likely successful).")
        return True
        
    except ElementTree.ParseError as e:
        raise RuntimeError(f"Invalid XML response from HVAC system: {e}")


def set_mode(mode: str, ip: str, password: str = DEFAULT_PASSWORD) -> bool:
    """
    Set the AC mode (fan/cool/heat).
    
    Checks the current status with lazy authentication,
    and then sends a command if the mode needs to be changed.
    
    Args:
        mode: The desired mode ('fan', 'cool', 'heat')
        ip: The IP address of the HVAC system
        password: The password for authentication
        
    Returns:
        True if mode was successfully changed or was already in that mode
        
    Raises:
        RuntimeError: If authentication fails, network request fails, or invalid mode
    """
    # Map text input to system numeric values
    mode_map = {
        "cool": "1",
        "heat": "2",
        "fan": "3"
    }
    
    mode_lower = mode.lower()
    if mode_lower not in mode_map:
        raise RuntimeError(f"Invalid mode '{mode}'. Must be one of: cool, heat, fan")
        
    target_mode = mode_map[mode_lower]
    
    # Check current status
    current_status = get_status(ip, password)
    if current_status["mode"] == target_mode:
        print(f"AC is already in {mode_lower.upper()} mode. No command sent.")
        return True
        
    url = f"http://{ip}/setSystemData?mode={target_mode}"
    
    try:
        xml_content = _make_request(url, ip, password)
        
        # Parse XML to verify the command was accepted
        root = ElementTree.fromstring(xml_content)
        request_element = root.find('.//request')
        
        if request_element is not None and request_element.text == "setSystemData":
            print(f"AC mode set to {mode_lower.upper()} successfully.")
            return True
            
        print("Command sent to HVAC system (response format unexpected but likely successful).")
        return True
        
    except ElementTree.ParseError as e:
        raise RuntimeError(f"Invalid XML response from HVAC system: {e}")


def set_fan_speed(speed: str, ip: str, password: str = DEFAULT_PASSWORD) -> bool:
    """
    Set the AC fan speed (low/med/high).
    
    Checks the current status with lazy authentication,
    and then sends a command if the fan speed needs to be changed.
    
    Args:
        speed: The desired fan speed ('low', 'med', 'high')
        ip: The IP address of the HVAC system
        password: The password for authentication
        
    Returns:
        True if fan speed was successfully changed or was already at that speed
        
    Raises:
        RuntimeError: If authentication fails, network request fails, or invalid speed
    """
    # Map text input to system numeric values
    fan_map = {
        "low": "1",
        "med": "2",
        "high": "3"
    }
    
    speed_lower = speed.lower()
    if speed_lower not in fan_map:
        raise RuntimeError(f"Invalid fan speed '{speed}'. Must be one of: low, med, high")
        
    target_speed = fan_map[speed_lower]
    
    # Check current status
    current_status = get_status(ip, password)
    if current_status["fan_speed"] == target_speed:
        print(f"AC fan speed is already {speed_lower.upper()}. No command sent.")
        return True
        
    url = f"http://{ip}/setSystemData?fanSpeed={target_speed}"
    
    try:
        xml_content = _make_request(url, ip, password)
        
        # Parse XML to verify the command was accepted
        root = ElementTree.fromstring(xml_content)
        request_element = root.find('.//request')
        
        if request_element is not None and request_element.text == "setSystemData":
            print(f"AC fan speed set to {speed_lower.upper()} successfully.")
            return True
            
        print("Command sent to HVAC system (response format unexpected but likely successful).")
        return True
        
    except ElementTree.ParseError as e:
        raise RuntimeError(f"Invalid XML response from HVAC system: {e}")


def get_status(ip: str, password: str = DEFAULT_PASSWORD) -> dict:
    """
    Get the current status of the AC (on or off), central temperatures, fan speed, and mode.
    
    Uses lazy authentication to retrieve system data
    and extract the required values.
    
    Args:
        ip: The IP address of the HVAC system
        password: The password for authentication
        
    Returns:
        A dictionary containing:
        - state: "ON" if AC is on (airconOnOff=1), "OFF" if AC is off (airconOnOff=0)
        - actual_temp: Central actual temperature
        - desired_temp: Central desired temperature
        - fan_speed: Current fan speed setting (1=low, 2=med, 3=high)
        - mode: Current mode setting (1=cooling, 2=heating, 3=fan only)
        
    Raises:
        RuntimeError: If authentication fails, network request fails, or status cannot be determined
    """
    url = f"http://{ip}/getSystemData"
    
    try:
        xml_content = _make_request(url, ip, password)
            
        # Parse XML and find values
        root = ElementTree.fromstring(xml_content)
        
        # Extract airconOnOff
        aircon_element = root.find('.//unitcontrol/airconOnOff')
        if aircon_element is None or aircon_element.text is None:
            # Let's see what the response actually was to help debug
            raise RuntimeError(f"Could not find valid 'airconOnOff' element in response. Raw XML: {xml_content[:500]}")
            
        status_value = aircon_element.text.strip()
        state = "ON" if status_value == "1" else "OFF"
        if status_value not in ["0", "1"]:
             raise RuntimeError(f"Unexpected airconOnOff value: {status_value}")
             
        # Extract central temperatures
        central_actual = root.find('.//unitcontrol/centralActualTemp')
        actual_temp = central_actual.text.strip() if central_actual is not None and central_actual.text is not None else "N/A"
        
        central_desired = root.find('.//unitcontrol/centralDesiredTemp')
        desired_temp = central_desired.text.strip() if central_desired is not None and central_desired.text is not None else "N/A"
        
        # Extract fan speed
        fan_element = root.find('.//unitcontrol/fanSpeed')
        fan_speed = fan_element.text.strip() if fan_element is not None and fan_element.text is not None else "unknown"
        
        # Extract mode
        mode_element = root.find('.//unitcontrol/mode')
        mode = mode_element.text.strip() if mode_element is not None and mode_element.text is not None else "unknown"
        
        return {
            "state": state,
            "actual_temp": actual_temp,
            "desired_temp": desired_temp,
            "fan_speed": fan_speed,
            "mode": mode
        }
            
    except ElementTree.ParseError as e:
        raise RuntimeError(f"Invalid XML response from HVAC system: {e}")


def get_zone_data(zone_number: int, ip: str, password: str = DEFAULT_PASSWORD) -> dict:
    """
    Get the data for a specific zone.
    
    Uses lazy authentication to retrieve zone data
    and returns it as a dictionary.
    
    Args:
        zone_number: The zone number (1-6)
        ip: The IP address of the HVAC system
        password: The password for authentication
        
    Returns:
        A dictionary containing zone information including:
        - name: Zone name
        - setting: 0=off, 1=on
        - actualTemp: Current temperature (may be empty if no sensor)
        - desiredTemp: Setpoint temperature
        - userPercentSetting: Damper percentage
        
    Raises:
        RuntimeError: If authentication fails or network request fails
    """
    url = f"http://{ip}/getZoneData?zone={zone_number}"
    
    try:
        xml_content = _make_request(url, ip, password)
            
        # Parse XML and extract zone data
        root = ElementTree.fromstring(xml_content)
        
        # Find the zone element (zone1, zone2, etc.)
        zone_element = root.find(f'.//zone{zone_number}')
        if zone_element is None:
            raise RuntimeError(f"Could not find zone{zone_number} element in response")
            
        result = {}
        
        # Extract name
        name_elem = zone_element.find('name')
        result['name'] = name_elem.text.strip() if name_elem is not None and name_elem.text is not None else f'Zone {zone_number}'
        
        # Extract setting (0=off, 1=on)
        setting_elem = zone_element.find('setting')
        result['setting'] = setting_elem.text.strip() if setting_elem is not None and setting_elem.text is not None else '0'
        
        # Extract actualTemp (may be empty for zones without temp sensors)
        actual_temp_elem = zone_element.find('actualTemp')
        result['actualTemp'] = actual_temp_elem.text.strip() if actual_temp_elem is not None and actual_temp_elem.text else ''
        
        # Extract desiredTemp
        desired_temp_elem = zone_element.find('desiredTemp')
        result['desiredTemp'] = desired_temp_elem.text.strip() if desired_temp_elem is not None and desired_temp_elem.text is not None else ''
        
        # Extract userPercentSetting (damper percentage)
        damper_elem = zone_element.find('userPercentSetting')
        result['userPercentSetting'] = damper_elem.text.strip() if damper_elem is not None and damper_elem.text is not None else '0'
        
        return result
            
    except ElementTree.ParseError as e:
        raise RuntimeError(f"Invalid XML response from HVAC system: {e}")


def set_zone_state(zone_number: int, state: int, ip: str, password: str = DEFAULT_PASSWORD) -> bool:
    """
    Set a zone on or off. State 1=ON, 0=OFF.
    """
    url = f"http://{ip}/setZoneData?zone={zone_number}&zoneSetting={state}"
    try:
        _make_request(url, ip, password)
        return True
    except Exception as e:
        print(f"Error setting zone {zone_number} state: {e}")
        return False


def set_zone_temp(zone_number: int, temp: float, ip: str, password: str = DEFAULT_PASSWORD) -> bool:
    """
    Set the desired temperature for a zone.
    """
    url = f"http://{ip}/setZoneData?zone={zone_number}&desiredTemp={temp}"
    try:
        _make_request(url, ip, password)
        return True
    except Exception as e:
        print(f"Error setting zone {zone_number} temp: {e}")
        return False


def set_zone_damper(zone_number: int, percent: int, ip: str, password: str = DEFAULT_PASSWORD) -> bool:
    """
    Set the damper percentage for a zone without a temperature sensor.
    """
    url = f"http://{ip}/setZoneData?zone={zone_number}&userPercentSetting={percent}"
    try:
        _make_request(url, ip, password)
        return True
    except Exception as e:
        print(f"Error setting zone {zone_number} damper: {e}")
        return False


def set_central_temp(temp: float, ip: str, password: str = DEFAULT_PASSWORD) -> bool:
    """
    Set the central desired temperature.
    """
    url = f"http://{ip}/setSystemData?centralDesiredTemp={temp}"
    try:
        _make_request(url, ip, password)
        return True
    except Exception as e:
        print(f"Error setting central temp: {e}")
        return False


def interactive_zone_control(ip: str, password: str = DEFAULT_PASSWORD):
    """
    Launch an interactive prompt to control zones and central temp.
    """
    try:
        # First gather zone names and types
        zones = {}
        print("Fetching current zone data...")
        for i in range(1, 7):
            try:
                z_data = get_zone_data(i, ip, password)
                
                actual_temp = z_data.get('actualTemp', '')
                is_temp_controlled = bool(actual_temp and actual_temp != "0.0")
                
                # Status is 1 for ON, 0 for OFF
                status_str = "ON " if z_data.get('setting') == '1' else "OFF"
                
                if is_temp_controlled:
                    val_str = f"{z_data.get('actualTemp', 'N/A')} / Set: {z_data.get('desiredTemp', 'N/A')}"
                else:
                    val_str = f"Damper: {z_data.get('userPercentSetting', '0')}%"
                
                zones[i] = {
                    'name': z_data['name'],
                    'has_sensor': is_temp_controlled,
                    'display': f"[{status_str}] {z_data['name']} ({val_str})"
                }
            except RuntimeError:
                pass # Zone might not exist
                
        # Also get central status
        status = get_status(ip, password)
        zones[7] = {
            'name': 'Central System',
            'has_sensor': True,
            'display': f"[---] Central System ({status['actual_temp']} / Set: {status['desired_temp']})"
        }
        
        while True:
            print("\n" + "="*40)
            print("Select a zone to control (or 0 to exit):")
            for z_num in sorted(zones.keys()):
                print(f"  {z_num}: {zones[z_num]['display']}")
            print("  0: Exit")
            
            choice = input("\nEnter zone number: ").strip()
            
            if choice == '0':
                break
                
            try:
                choice_num = int(choice)
                if choice_num not in zones:
                    print("Invalid selection.")
                    continue
            except ValueError:
                print("Please enter a number.")
                continue
                
            selected = zones[choice_num]
            
            print(f"\n--- Control {selected['name']} ---")
            if choice_num == 7:
                 print("Enter target temperature (e.g. 23.0) or 0 to skip:")
            elif selected['has_sensor']:
                print("Enter target temperature (e.g. 23.0) or 0 to turn OFF:")
            else:
                print("Enter target damper % (e.g. 50) or 0 to turn OFF:")
                
            val_input = input("> ").strip()
            
            if not val_input:
                continue
                
            try:
                target_val = float(val_input)
            except ValueError:
                print("Invalid number format.")
                continue
                
            if choice_num == 7:
                if target_val > 0:
                    set_central_temp(target_val, ip, password)
            else:
                if target_val == 0:
                    set_zone_state(choice_num, 0, ip, password)
                else:
                    # Make sure it's turned on first
                    set_zone_state(choice_num, 1, ip, password)
                    
                    if selected['has_sensor']:
                        set_zone_temp(choice_num, target_val, ip, password)
                    else:
                        set_zone_damper(choice_num, int(target_val), ip, password)
            
            print("Command sent. (Note: changes may take a moment to reflect in status)")
            
    except Exception as e:
        print(f"\nError in interactive mode: {e}")


def main():
    """Main entry point for the HVAC control script."""
    
    parser = argparse.ArgumentParser(
        description="Control myAir/iZS10.3 HVAC system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python hvac_control_auth.py --on                  # Turn AC on
    python hvac_control_auth.py --off                 # Turn AC off
    python hvac_control_auth.py --mode heat           # Set AC to heat mode
    python hvac_control_auth.py --fan high            # Set fan speed to high
    python hvac_control_auth.py --zone                # Open interactive zone control
    python hvac_control_auth.py --status              # Check current status
    python hvac_control_auth.py --ip 192.168.1.X ...  # Specify custom IP
        """
    )
    
    parser.add_argument(
        '--ip', '-i',
        default='192.168.1.209',
        help='IP address of the HVAC system (default: 192.168.1.209)'
    )
    
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument(
        '--on',
        action='store_true',
        help='Turn the AC on'
    )
    action_group.add_argument(
        '--off',
        action='store_true',
        help='Turn the AC off'
    )
    action_group.add_argument(
        '--status',
        action='store_true',
        help='Check current AC status (on or off)'
    )
    action_group.add_argument(
        '--mode',
        choices=['cool', 'heat', 'fan'],
        help='Set the AC mode (cool, heat, fan)'
    )
    action_group.add_argument(
        '--fan',
        choices=['low', 'med', 'high'],
        help='Set the AC fan speed (low, med, high)'
    )
    action_group.add_argument(
        '--zone',
        action='store_true',
        help='Launch interactive zone control to set temp/damper or turn zones on/off'
    )
    
    args = parser.parse_args()
    
    try:
        if args.on:
            turn_on(args.ip)
        elif args.off:
            turn_off(args.ip)
        elif args.mode:
            set_mode(args.mode, args.ip)
        elif args.fan:
            set_fan_speed(args.fan, args.ip)
        elif args.zone:
            interactive_zone_control(args.ip)
        elif args.status:
            status = get_status(args.ip)
            print(f"AC Status: {status['state']}")
            
            # Map numeric mode to text
            mode_map = {"1": "COOL", "2": "HEAT", "3": "FAN"}
            mode_text = mode_map.get(status['mode'], f"Unknown ({status['mode']})")
            
            # Map numeric fan speed to text
            fan_map = {"1": "LOW", "2": "MED", "3": "HIGH"}
            fan_text = fan_map.get(status['fan_speed'], f"Unknown ({status['fan_speed']})")
            
            print(f"Mode: {mode_text} | Fan: {fan_text}")
            print(f"Central Temp: {status['actual_temp']}/{status['desired_temp']}")
            
            print("\nZone Status:")
            for i in range(1, 7):
                try:
                    zone_data = get_zone_data(i, args.ip)
                    
                    # Status is 1 for ON, 0 for OFF
                    status_str = "ON " if zone_data.get('setting') == '1' else "OFF"
                    
                    # Check if actualTemp is "0.0" or empty, which indicates no temperature sensor
                    actual_temp = zone_data.get('actualTemp', '')
                    if not actual_temp or actual_temp == "0.0":
                        # No temp sensor, use damper percentage
                        damper = zone_data.get('userPercentSetting', '0')
                        temp_str = f"{damper}% (Damper)"
                    else:
                        # Has temp sensor, use current/setpoint
                        desired_temp = zone_data.get('desiredTemp', 'N/A')
                        temp_str = f"{actual_temp}/{desired_temp}"
                    
                    print(f"[{status_str}] {zone_data['name']}: {temp_str}")
                except RuntimeError as e:
                    # Some zones might not exist or fail, we can just skip or report them
                    print(f"Zone {i}: Could not retrieve data ({e})")
            
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
