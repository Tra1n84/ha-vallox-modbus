# Vallox Modbus for Home Assistant

A Home Assistant custom integration for Vallox MV ventilation units
(MyVallox control) over **Modbus RTU**. It uses the
[`vallox-modbus`](https://github.com/Tra1n84/vallox-modbus) library and the
shared Modbus connections of Home Assistant's `modbus` integration.

The core [Vallox integration](https://www.home-assistant.io/integrations/vallox)
talks to the same units over the network (MyVallox WebSocket). This
integration is for installations that use the unit's RS485 Modbus line
instead. Its entity names, keys and units follow the core integration, so
entity IDs such as `fan.vallox` and `sensor.vallox_extract_air` stay the same.

## Requirements

- Home Assistant 2026.10.0 or newer.
- A Vallox MV unit with MyVallox control.
- An RS485 adapter on the Home Assistant host, for example a USB-RS485
  adapter.

Vallox MV units speak Modbus RTU only. The Vallox Modbus manual states that the
MV control has no Modbus TCP option.

## Tested hardware

| Unit | Connection | Settings |
| --- | --- | --- |
| Vallox ValloPlus 510 MV | Modbus RTU over a USB-RS485 adapter | Unit ID 1, 19200 baud, 8 data bits, even parity, 1 stop bit |

Other Vallox MV models and firmware versions use the same documented
registers but have not been tested. Reports are welcome in the
[issue tracker](https://github.com/Tra1n84/ha-vallox-modbus/issues).

## Wiring

According to the wiring diagram in the Vallox Modbus manual:

- Connect the adapter's **A** line to **A** on the unit and **B** to **B**.
- Up to 32 Vallox units can share one Modbus line. Chain them as a bus
  (A to A, B to B), not as a star.
- Terminate the line with a **120 Ω** resistor. Many RS485 adapters have a
  switchable or built-in termination resistor.
- Use a twisted-pair cable for A and B.

If the unit does not answer, swap A and B first: adapters do not label the
lines consistently.

## Unit settings

Set the Modbus parameters on the unit, either on the MyVallox Control panel
(**Settings → Expert settings → Modbus settings**) or in the web interface
(**Expert settings → Modbus settings**):

| Setting | Options | Default in this integration |
| --- | --- | --- |
| Modbus address | 1–247 | 1 |
| Baud rate | 9600, 19200, 38400, 57600, 115200 | 19200 |
| Parity | none, even, odd | even |
| Stop bits | 1, 2 | 1 |

The connection always uses 8 data bits.

## Installation

### HACS

1. In HACS, open the menu and choose **Custom repositories**.
2. Add `https://github.com/Tra1n84/ha-vallox-modbus` with the type
   **Integration**.
3. Install **Vallox Modbus** and restart Home Assistant.

### Manual

Copy `custom_components/vallox_modbus` into the `custom_components` folder
of your Home Assistant configuration and restart Home Assistant.

## Configuration

1. Go to **Settings → Devices & services → Add integration** and choose
   **Vallox Modbus**.
2. Enter the settings:
   - **Serial port**: the RS485 adapter. Prefer a stable
     `/dev/serial/by-id/...` path over `/dev/ttyUSB0`.
   - **Baud rate**, **Parity**, **Stop bits**: as set on the unit.
   - **Modbus unit ID**: the Modbus address set on the unit.
3. The integration reads the unit once, without writing, and checks that the
   values look like a Vallox MV unit before it creates the entry.

Each unit ID on a serial port can be added once. Several units on one bus get
one entry each and share the serial connection.

If the unit is currently set up through the YAML `modbus:` integration,
disable that hub first: the integration refuses a serial port that a YAML hub
uses.

To change the settings later, open the entry and choose **Reconfigure**.

## Entities

| Platform | Entities |
| --- | --- |
| Fan | Ventilation: on/off, profile speed in percent, presets Home, Away, Boost, Fireplace, Extra, Auto |
| Sensor | Extract, exhaust, outdoor, supply and supply cell air temperature; humidity; current profile; fan speed; cell state; profile duration; remaining time for filter; filter time remaining |
| Sensor (disabled by default) | Optional air temperature, CO2, extract and supply fan speed in RPM |
| Binary sensor | Defrosting, Fault |
| Number | Supply air temperature (Home, Away, Boost); fan speed (Home, Away, Boost) |
| Number (disabled by default) | Supply air temperature (Extra); extract and supply fan speed (Extra); Boost, Fireplace and Extra duration |

As in the core Vallox integration, the fan percentage is the configured fan
speed of the active profile. The **Fan speed** sensor shows the current fan
speed and reads 0 while the unit is switched off.

The number entities only cover settings whose writes have been validated on
hardware.

## Data updates

The integration polls the unit:

- measurements, profile, timers and inputs every 60 seconds,
- profile settings and configuration every 10 minutes, or after 60 seconds if
  the previous poll failed.

After a change from Home Assistant, the affected values are read again right
away. Changes made on the control panel appear with the next poll. If some
registers fail to answer, only the affected entities become unavailable.

## Known limitations

- **Preset changes are not atomic.** Selecting a preset writes several
  registers in a row (profile and timers); this is validated on hardware for
  every preset. If a write fails halfway, Home Assistant reports an error and
  reads the state again.
- **Extra on the control panel.** Extra is the unit's programmable input
  mode. While it is active, the MyVallox Control panel keeps showing the
  previous mode with an additional symbol, while the fan shows Extra. The panel
  can neither select Extra nor switch its timer function.
- **No fan speed in Auto, Fireplace and Extra.** These profiles have no single
  fan speed setting (Fireplace and Extra set supply and extract air
  separately), so, as in the core integration, the fan shows no percentage and
  rejects setting one while they are active. The *Fan speed* sensor shows the
  actual speed.
- **Profile duration needs the profile's timer.** Boost, Fireplace and Extra
  run for their configured duration only while the profile's timer function is
  on. For Boost and Fireplace, the MyVallox Control panel shows it as the
  first screen of the mode settings (Info, then the pen icon); Fireplace is
  called Custom mode there. While the timer function is off, the profile runs
  until the mode is changed and *Profile duration* is unknown.
- **Not available over Modbus**, compared with the core integration: the
  extract efficiency sensor, the post-heater binary sensor, the bypass lock
  switch, a writable filter change date, the profile actions, and device
  model, software version and serial number.

## Troubleshooting

- **Failed to connect**: check the serial port, the wiring (swap A and B), the
  termination and that baud rate, parity and stop bits match the unit.
- **Not a Vallox MV unit**: the unit answered with implausible values. Check
  the unit ID.
- **Serial port in use**: another integration uses the same serial port with
  different settings. All Modbus devices on one bus must use the same baud
  rate, parity and stop bits.
- **Serial port used by a YAML Modbus hub**: a hub under `modbus:` in
  `configuration.yaml` opens the serial port on its own, and two Modbus
  masters on one port interfere with each other. The integration therefore
  refuses that port. Comment out the hub, restart Home Assistant and add or
  reload the entry. To go back to YAML, delete the entry first.
- **Slow updates**: the unit can leave single requests unanswered. The
  integration resends them, which delays the update but keeps the entities
  available. Set the `vallox_modbus.retry` logger to `debug` to see each
  resent request.
- For details, enable debug logging for the integration and download the
  diagnostics of the entry. Diagnostics contain the raw register values but
  not the serial port path.

## Removal

1. Go to **Settings → Devices & services → Vallox Modbus**.
2. Open the entry menu and choose **Delete**.
3. To remove the files as well, uninstall the integration in HACS, or delete
   `custom_components/vallox_modbus`, and restart Home Assistant.

## Development

See [docs/entity-mapping.md](docs/entity-mapping.md) for how the entities map
to the core integration, the Vallox metrics and the Modbus registers.

```bash
scripts/setup        # Python 3.14 and the test environment via uv
uv run pytest        # tests, no hardware needed
uv run ruff check .
uv run ruff format --check .
```

`scripts/setup` keeps the uv cache in `/tmp/uv-cache`, which suits
environments with little space in `$HOME` such as Google Cloud Shell. Export
the same `UV_CACHE_DIR` and `UV_LINK_MODE=copy` for later uv commands.

## License

MIT
