# Home Assistant Integration Plan: myAir / iZS10.3

## 1. Project Structure
The integration will be a Home Assistant Custom Component, structured as follows:
```text
custom_components/myair_izs103/
├── __init__.py           # Setup and initialization, coordinator setup
├── manifest.json         # Integration metadata (domain, version, dependencies)
├── config_flow.py        # UI configuration flow (IP, Password input)
├── const.py              # Constants (Domain, defaults, URLs)
├── coordinator.py        # DataUpdateCoordinator for polling the API
├── climate.py            # Main AC and Zone climate entities
├── fan.py                # Zone damper controls (if no temp sensor)
└── api.py                # Async API client (refactored from hvac_control_auth.py)
```

## 2. API Refactoring (`api.py`)
- Convert the synchronous `urllib` requests to asynchronous `aiohttp` requests, as Home Assistant requires async operations to prevent blocking the event loop.
- Implement lazy authentication within the async client.
- Refactor XML parsing (e.g., using `xml.etree.ElementTree` or `defusedxml`).
- Return strongly-typed data structures (dicts/dataclasses) for the coordinator.

## 3. Config Flow (`config_flow.py`)
- Implement a UI configuration flow so users can add the integration via the Home Assistant UI.
- Prompt for **IP Address** and **Password** (default "password").
- Test the connection during setup to validate credentials before saving.

## 4. DataUpdateCoordinator (`coordinator.py`)
- Set up a single polling mechanism (e.g., every 30-60 seconds) to fetch `getSystemData` and `getZoneData` for all 6 zones.
- This prevents the integration from overwhelming the HVAC system with requests and ensures all entities update simultaneously.

## 5. Entities mapping
### Central HVAC (`climate.py`)
- **Type**: `ClimateEntity`
- **Supported Features**: `Turn On/Off`, `Target Temperature`, `HVAC Mode` (Cool, Heat, Fan Only), `Fan Mode` (Low, Medium, High).
- **State Mapping**:
  - `airconOnOff=1` -> `HVACMode.COOL`/`HEAT`/`FAN_ONLY`
  - `airconOnOff=0` -> `HVACMode.OFF`

### Zones with Temperature Sensors (`climate.py`)
- **Type**: `ClimateEntity`
- **Supported Features**: `Turn On/Off`, `Target Temperature`.
- Uses `getZoneData` fields: `actualTemp` and `desiredTemp`.

### Zones without Temperature Sensors (`fan.py` or `number.py`)
- **Type**: `FanEntity` (using percentage) or `NumberEntity`
- Maps the `userPercentSetting` (0-100%) damper value to Home Assistant.

## 6. Development Steps
1. Setup a local Home Assistant development environment.
2. Build the async API wrapper (`api.py`).
3. Create the foundational files (`manifest.json`, `const.py`, `__init__.py`).
4. Implement the `ConfigFlow` to allow adding the integration.
5. Create the `DataUpdateCoordinator` to manage polling.
6. Implement the `Climate` platform for the central unit.
7. Implement the `Climate`/`Fan` platforms for the zones.
8. Test against the local device.