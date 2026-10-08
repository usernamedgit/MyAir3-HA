# ⚠️ USE AT YOUR OWN RISK ⚠️

> [!WARNING]
> **This integration was 100% vibe coded.** It was written entirely by an AI, and the repo owner has no idea what the code is doing. It has not been reviewed by a human who understands it. It controls real heating and cooling equipment. Use it at your own risk.

# myAir 3 / iZS10.3 for Home Assistant

A Home Assistant integration for the myAir 3 (iZS10.3) zoned air-conditioning controller. It talks to the controller over your local network and polls it every 30 seconds.

## What you get

- **The air conditioner**: a thermostat with off / cool / heat / fan only, fan speed (low, medium, high) and the central setpoint.
- **Zones with a temperature sensor**: a thermostat per zone. A zone has no mode of its own, so it offers just off and whatever mode the central unit is in, and shows idle when the unit is off.
- **Zones without a sensor**: an on/off switch and a damper slider (%).
- **Diagnostics**: aircon fault (with error code), damper motor fault per zone, and battery and signal for each zone sensor.

## Install with HACS

1. In HACS, open the menu (⋮) → **Custom repositories**.
2. Add `https://github.com/usernamedgit/MyAir3-Python` with type **Integration**.
3. Find **myAir 3 / iZS10.3** in HACS, download it, and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration → myAir 3**, then enter the controller's IP address and password (the factory default is `password`).

Updates appear in HACS like any other integration.

## Manual install

Copy `custom_components/myair3` into your Home Assistant `config/custom_components/` folder and restart Home Assistant.

## Other files in this repo

- `hvac_control_auth.py`: a command-line tool for the controller.
- `myAir_commands.txt`: captured controller URLs and sample responses.

## Development

```
python3.13 -m venv .venv && .venv/bin/pip install -r requirements-test.txt
.venv/bin/pytest
```

The tests run the integration inside Home Assistant against a simulated controller (`tests/conftest.py`).
