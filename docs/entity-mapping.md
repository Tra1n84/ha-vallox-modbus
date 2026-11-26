# Entity Mapping

How the entities of this integration relate to the core `vallox` integration
(WebSocket backend), the Vallox metric names (`A_CYC_*`) used by
`vallox_websocket_api`, the Modbus registers and the `vallox-modbus` API.

Assessed on 2026-11-22 against core `vallox` on `dev`, `vallox_websocket_api`
7.0.0 data models 2.0.16 and 2.0.22, the Vallox Modbus manual D5269
(20.04.2020) and `vallox-modbus` 0.2.0. `vallox-modbus` 0.2.2 reads and
writes the same registers.

## Identity

| Item | Core `vallox` | `vallox_modbus` |
| --- | --- | --- |
| Domain | `vallox` | `vallox_modbus` |
| Device identifier | unit UUID (`A_CYC_UUID0..7`) | config entry ID |
| Entity unique ID | `<uuid>-<key>`, fan: `<uuid>` | `<entry_id>-<key>`, fan: `<entry_id>` |
| Device name | `Vallox` | `Vallox` (entry title) |
| Model, SW version | `A_CYC_MACHINE_MODEL`, `A_CYC_APPL_SW_VERSION_*` | not available |

The UUID (8214–8221), model (17), software version (2–10) and serial number
(14–15) registers are not documented in the Vallox Modbus manual, so the
library does not read them. Keys, translation keys and the device name match
core, so entity IDs match too (`fan.vallox`, `sensor.vallox_extract_air`).

## Register addresses and scaling

All 77 registers that `vallox-modbus` 0.2.0 reads or writes have an `A_CYC_*`
name at the same address in both WebSocket data models. There are no address
deviations.

| Topic | WebSocket | Modbus |
| --- | --- | --- |
| Temperatures | centi-Kelvin, read values rounded to 0.1 °C | centi-Kelvin, 0.01 °C; shown with one decimal |
| `A_CYC_RH_VALUE`, `A_CYC_CO2_VALUE` | 0 reported as 0 | 0 reported as unknown (no sensor) |
| `A_CYC_STATE` 4609 | 0 Home, 1 Away, 2 Auto | 0 Home, 1 Away, 2 Automatic; 2 validated on hardware |
| `A_CYC_MODE` 4610 | on unless 5 | 0 normal, 5 off; other values unknown |
| Profile priority | Extra > Fireplace > Boost > basic | same, as documented in the manual |
| Profile enum | `Profile.HOME = 1` ... | `Profile.HOME = 0` ...; translate by meaning |

## Mapping

Status: ✅ available and validated on hardware · ⚠️ available, not or only
partly validated on hardware · ⛔ not available

The status covers reads and, where the entity writes, writes. Sensor and
binary sensor entities only read. The validation status follows
`vallox-modbus/docs/hardware-validation.md` as of 2026-11-26.

The tables are grouped by platform and use the `A_CYC_*` names without the
prefix. *Not in core* marks entities without a counterpart in the core
`vallox` integration, *disabled* marks entities disabled by default.

### Fan

The core `ventilation` fan maps to the single fan entity.

| Feature | `A_CYC_*` | Register | `vallox-modbus` | Status |
| --- | --- | --- | --- | --- |
| on/off | `MODE` | 4610 | `runtime.system_mode`<br>`async_set_power` | ✅ |
| preset (read) | `STATE`<br>`*_TIMER` | 4609<br>4612–4614 | `profile` | ✅ |
| preset home, away, boost, fireplace, extra | `STATE`<br>`*_TIMER`<br>`*_TIME` | 4609<br>4612–4614<br>20544, 20545, 20496 | `async_set_profile` | ✅ |
| preset auto | `STATE` = 2<br>`*_TIMER` = 0 | 4609<br>4612–4614 | `async_set_profile(Profile.AUTOMATIC)` | ✅ |
| percentage, attributes `fan_speed_*` | `*_SPEED_SETTING` | 20501, 20507, 20513 | `settings.*_fan_speed`<br>`async_set_*_fan_speed` | ✅ |

### Sensor

| Key | `A_CYC_*` | Register | `vallox-modbus` | Status |
| --- | --- | --- | --- | --- |
| `extract_air` | `TEMP_EXTRACT_AIR` | 4354 | `measurements.extract_air_temperature` | ✅ |
| `exhaust_air` | `TEMP_EXHAUST_AIR` | 4355 | `measurements.exhaust_air_temperature` | ✅ |
| `outdoor_air` | `TEMP_OUTDOOR_AIR` | 4356 | `measurements.outdoor_air_temperature` | ✅ |
| `supply_cell_air` | `TEMP_SUPPLY_CELL_AIR` | 4357 | `measurements.supply_cell_air_temperature` | ✅ |
| `supply_air` | `TEMP_SUPPLY_AIR` | 4358 | `measurements.supply_air_temperature` | ✅ |
| `optional_air`<br>disabled | `TEMP_OPTIONAL` | 4389 | `sensors.optional_temperature` | ✅ |
| `humidity` | `RH_VALUE` | 4363 | `measurements.humidity` | ✅ |
| `co2`<br>disabled | `CO2_VALUE` | 4364 | `measurements.co2` | ✅ |
| `efficiency` | `EXTRACT_EFFICIENCY` | 32776 | — | ⛔ not in manual |
| `current_profile` | derived | 4609<br>4612–4614 | `profile` | ✅ |
| `fan_speed` | `FAN_SPEED`<br>`MODE` | 4353<br>4610 | `measurements.fan_speed` | ✅ |
| `extract_fan_speed`<br>disabled | `EXTR_FAN_SPEED` | 4361 | `measurements.extract_fan_rpm` | ✅ |
| `supply_fan_speed`<br>disabled | `SUPP_FAN_SPEED` | 4362 | `measurements.supply_fan_rpm` | ✅ |
| `remaining_time_for_filter` | `FILTER_CHANGED_*`<br>`FILTER_CHANGE_INTERVAL` | 20546–20548<br>20537 | `next_filter_change_date` | ✅ |
| `cell_state` | `CELL_STATE` | 4616 | `runtime.heat_exchanger_state` | ✅ |
| `profile_duration` | `*_TIMER`<br>`*_TIMER_ENABLED` | 4612–4614<br>21766, 21767, 21772 | `remaining_profile_duration` | ⚠️ off state of 21772 not observed |
| `filter_remaining`<br>not in core | `REMAINING_TIME_FOR_FILTER` | 4620 | `runtime.filter_remaining` | ✅ |

### Binary sensor

| Key | `A_CYC_*` | Register | `vallox-modbus` | Status |
| --- | --- | --- | --- | --- |
| `post_heater` | `IO_HEATER` | 4868 | — | ⛔ not in manual |
| `defrosting`<br>not in core | `DEFROSTING` | 4611 | `runtime.defrosting` | ✅ |
| `fault`<br>not in core | `LIMP_MODE` | 4621 | `runtime.fault` | ✅ |

### Number

| Key | `A_CYC_*` | Register | `vallox-modbus` | Status |
| --- | --- | --- | --- | --- |
| `supply_air_target_home` | `HOME_AIR_TEMP_TARGET` | 20508 | `async_set_home_air_temperature_target` | ✅ |
| `supply_air_target_away` | `AWAY_AIR_TEMP_TARGET` | 20502 | `async_set_away_air_temperature_target` | ✅ |
| `supply_air_target_boost` | `BOOST_AIR_TEMP_TARGET` | 20514 | `async_set_boost_air_temperature_target` | ✅ |
| `supply_air_target_extra`<br>not in core, disabled | `EXTRA_AIR_TEMP_TARGET` | 20493 | `async_set_extra_air_temperature_target` | ✅ |
| `fan_speed_home`<br>not in core | `HOME_SPEED_SETTING` | 20507 | `async_set_home_fan_speed` | ✅ |
| `fan_speed_away`<br>not in core | `AWAY_SPEED_SETTING` | 20501 | `async_set_away_fan_speed` | ✅ |
| `fan_speed_boost`<br>not in core | `BOOST_SPEED_SETTING` | 20513 | `async_set_boost_fan_speed` | ✅ |
| `extra_extract_fan`<br>not in core, disabled | `EXTRA_EXTR_FAN` | 20494 | `async_set_extra_extract_fan` | ✅ |
| `extra_supply_fan`<br>not in core, disabled | `EXTRA_SUPP_FAN` | 20495 | `async_set_extra_supply_fan` | ✅ |
| `boost_duration`<br>not in core, disabled | `BOOST_TIME` | 20544 | `async_set_boost_duration` | ✅ |
| `fireplace_duration`<br>not in core, disabled | `FIREPLACE_TIME` | 20545 | `async_set_fireplace_duration` | ✅ |
| `extra_duration`<br>not in core, disabled | `EXTRA_TIME` | 20496 | `async_set_extra_duration` | ✅ |

### Not exposed

Core entities and actions without a counterpart in this integration:

| Core entity | `A_CYC_*` | Register | `vallox-modbus` | Status |
| --- | --- | --- | --- | --- |
| switch `bypass_locked` | `BYPASS_LOCKED` | 20552 | `async_set_bypass_locked` | ⛔ write not validated, left out in v1 |
| date `filter_change_date` | `FILTER_CHANGED_*` | 20546–20548 | no write in 0.2.2 | ⛔ |
| actions `set_profile_fan_speed_*`, `set_profile` | — | — | setters, `async_set_profile` | ⛔ not in v1 |

The remaining registers (Modbus and installation configuration, RH, CO2 and
VOC sensor arrays, raw input values) are only included in the diagnostics.

## Open library work

- Hardware validation of the timer switch read of 21772 in the off state.
- Hardware validation of `async_set_profile` with an explicit duration and of
  the timer switch writes. The fan presets do not use them.
- Filter change date write, for the core `filter_change_date` date entity:
  implemented in the library but not yet released or validated on hardware.
- Bypass lock write validation, for the core `bypass_locked` switch.
- Hardware validation of the Boost preset while the unit is defrosting. The
  control panel does not start Boost then.
- Release of the request timing validated on hardware (1 second timeout,
  500 ms between requests, up to 5 resends), which shortens updates with
  unanswered requests.
- A hardware read test of the undocumented identity, efficiency (32776) and
  post-heater (4868) registers.
