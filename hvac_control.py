#!/usr/bin/env python3
"""
HVAC Control Script for myAir 3 System

This script provides command-line control of a myAir HVAC system,
allowing users to turn the AC on/off and check its status.

Usage:
    python hvac_control.py --ip 192.168.1.100 --on      # Turn AC on
    python hvac_control.py --ip 192.168.1.100 --off     # Turn AC off
    python hvac_control.py --ip 192.168.1.100 --status  # Check current status

The HVAC system requires authentication before any control commands can be sent.
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
        
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to connect to HVAC system at {ip}: {e.reason}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HVAC system returned HTTP error {e.code} during authentication")
    except ElementTree.ParseError as e:
        raise RuntimeError(f"Invalid XML response from HVAC system: {e}")


def turn_on(ip: str, password: str = DEFAULT_PASSWORD) -> bool:
    """
    Turn the AC on.
    
    First authenticates with the HVAC system, checks the current status,
    and then sends a command to set airconOnOff=1 if it's not already on.
    
    Args:
        ip: The IP address of the HVAC system
        password: The password for authentication
        
    Returns:
        True if AC was successfully turned on or was already on
        
    Raises:
        RuntimeError: If authentication fails or network request fails
    """
    # Authenticate first
    if not authenticate(ip, password):
        raise RuntimeError("Authentication failed. Cannot turn on AC.")
        
    # Check current status
    current_status = get_status(ip, password)
    if current_status["state"] == "ON":
        print("AC is already ON. No command sent.")
        return True
    
    url = f"http://{ip}/setSystemData?airconOnOff=1"
    
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT) as response:
            xml_content = response.read().decode('utf-8')
            
        # Parse XML to verify the command was accepted
        root = ElementTree.fromstring(xml_content)
        request_element = root.find('.//request')
        
        if request_element is not None and request_element.text == "setSystemData":
            print("AC turned ON successfully.")
            return True
            
        print("Command sent to HVAC system (response format unexpected but likely successful).")
        return True
        
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to connect to HVAC system at {ip}: {e.reason}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HVAC system returned HTTP error {e.code} while turning on AC")
    except ElementTree.ParseError as e:
        raise RuntimeError(f"Invalid XML response from HVAC system: {e}")


def turn_off(ip: str, password: str = DEFAULT_PASSWORD) -> bool:
    """
    Turn the AC off.
    
    First authenticates with the HVAC system, checks the current status,
    and then sends a command to set airconOnOff=0 if it's not already off.
    
    Args:
        ip: The IP address of the HVAC system
        password: The password for authentication
        
    Returns:
        True if AC was successfully turned off or was already off
        
    Raises:
        RuntimeError: If authentication fails or network request fails
    """
    # Authenticate first
    if not authenticate(ip, password):
        raise RuntimeError("Authentication failed. Cannot turn off AC.")
        
    # Check current status
    current_status = get_status(ip, password)
    if current_status["state"] == "OFF":
        print("AC is already OFF. No command sent.")
        return True
    
    url = f"http://{ip}/setSystemData?airconOnOff=0"
    
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT) as response:
            xml_content = response.read().decode('utf-8')
            
        # Parse XML to verify the command was accepted
        root = ElementTree.fromstring(xml_content)
        request_element = root.find('.//request')
        
        if request_element is not None and request_element.text == "setSystemData":
            print("AC turned OFF successfully.")
            return True
            
        print("Command sent to HVAC system (response format unexpected but likely successful).")
        return True
        
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to connect to HVAC system at {ip}: {e.reason}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HVAC system returned HTTP error {e.code} while turning off AC")
    except ElementTree.ParseError as e:
        raise RuntimeError(f"Invalid XML response from HVAC system: {e}")


def get_status(ip: str, password: str = DEFAULT_PASSWORD) -> dict:
    """
    Get the current status of the AC (on or off) and central temperatures.
    
    First authenticates with the HVAC system, then retrieves system data
    and extracts the airconOnOff, centralActualTemp, and centralDesiredTemp values.
    
    Args:
        ip: The IP address of the HVAC system
        password: The password for authentication
        
    Returns:
        A dictionary containing:
        - state: "ON" if AC is on (airconOnOff=1), "OFF" if AC is off (airconOnOff=0)
        - actual_temp: Central actual temperature
        - desired_temp: Central desired temperature
        
    Raises:
        RuntimeError: If authentication fails, network request fails, or status cannot be determined
    """
    # Authenticate first
    if not authenticate(ip, password):
        raise RuntimeError("Authentication failed. Cannot get status.")
    
    url = f"http://{ip}/getSystemData"
    
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT) as response:
            xml_content = response.read().decode('utf-8')
            
        # Parse XML and find values
        root = ElementTree.fromstring(xml_content)
        
        # Extract airconOnOff
        aircon_element = root.find('.//unitcontrol/airconOnOff')
        if aircon_element is None:
            raise RuntimeError("Could not find 'airconOnOff' element in response")
            
        status_value = aircon_element.text.strip()
        state = "ON" if status_value == "1" else "OFF"
        if status_value not in ["0", "1"]:
             raise RuntimeError(f"Unexpected airconOnOff value: {status_value}")
             
        # Extract central temperatures
        central_actual = root.find('.//unitcontrol/centralActualTemp')
        actual_temp = central_actual.text.strip() if central_actual is not None else "N/A"
        
        central_desired = root.find('.//unitcontrol/centralDesiredTemp')
        desired_temp = central_desired.text.strip() if central_desired is not None else "N/A"
        
        return {
            "state": state,
            "actual_temp": actual_temp,
            "desired_temp": desired_temp
        }
            
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to connect to HVAC system at {ip}: {e.reason}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HVAC system returned HTTP error {e.code} while getting status")
    except ElementTree.ParseError as e:
        raise RuntimeError(f"Invalid XML response from HVAC system: {e}")


def get_zone_data(zone_number: int, ip: str, password: str = DEFAULT_PASSWORD) -> dict:
    """
    Get the data for a specific zone.
    
    First authenticates with the HVAC system, then retrieves zone data
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
    # Authenticate first
    if not authenticate(ip, password):
        raise RuntimeError("Authentication failed. Cannot get zone data.")
    
    url = f"http://{ip}/getZoneData?zone={zone_number}"
    
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT) as response:
            xml_content = response.read().decode('utf-8')
            
        # Parse XML and extract zone data
        root = ElementTree.fromstring(xml_content)
        
        # Find the zone element (zone1, zone2, etc.)
        zone_element = root.find(f'.//zone{zone_number}')
        if zone_element is None:
            raise RuntimeError(f"Could not find zone{zone_number} element in response")
            
        result = {}
        
        # Extract name
        name_elem = zone_element.find('name')
        result['name'] = name_elem.text.strip() if name_elem is not None else f'Zone {zone_number}'
        
        # Extract setting (0=off, 1=on)
        setting_elem = zone_element.find('setting')
        result['setting'] = setting_elem.text.strip() if setting_elem is not None else '0'
        
        # Extract actualTemp (may be empty for zones without temp sensors)
        actual_temp_elem = zone_element.find('actualTemp')
        result['actualTemp'] = actual_temp_elem.text.strip() if actual_temp_elem is not None and actual_temp_elem.text else ''
        
        # Extract desiredTemp
        desired_temp_elem = zone_element.find('desiredTemp')
        result['desiredTemp'] = desired_temp_elem.text.strip() if desired_temp_elem is not None else ''
        
        # Extract userPercentSetting (damper percentage)
        damper_elem = zone_element.find('userPercentSetting')
        result['userPercentSetting'] = damper_elem.text.strip() if damper_elem is not None else '0'
        
        return result
            
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to connect to HVAC system at {ip}: {e.reason}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HVAC system returned HTTP error {e.code} while getting zone data")
    except ElementTree.ParseError as e:
        raise RuntimeError(f"Invalid XML response from HVAC system: {e}")


def main():
    """Main entry point for the HVAC control script."""
    
    parser = argparse.ArgumentParser(
        description="Control myAir 3 HVAC system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python hvac_control.py --ip 192.168.1.100 --on      # Turn AC on
    python hvac_control.py --ip 192.168.1.100 --off     # Turn AC off
    python hvac_control.py --ip 192.168.1.100 --status  # Check current status
        """
    )
    
    parser.add_argument(
        '--ip', '-i',
        default='192.168.1.100',
        help='IP address of the HVAC system (default: 192.168.1.100)'
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
    
    args = parser.parse_args()
    
    try:
        if args.on:
            turn_on(args.ip)
        elif args.off:
            turn_off(args.ip)
        elif args.status:
            status = get_status(args.ip)
            print(f"AC Status: {status['state']}")
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
