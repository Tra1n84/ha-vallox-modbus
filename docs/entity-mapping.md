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

Status: ✅ available, writes validated on hardware · 🟡 read only · ⚠️ write
not validated on hardware · ⛔ not available

| Core entity (key) | `A_CYC_*` | Register | `vallox-modbus` | `vallox_modbus` entity | Status |
| --- | --- | --- | --- | --- | --- |
| fan `ventilation` on/off | `MODE` | 4610 | `runtime.system_mode`, `async_set_power` | fan | ✅ |
| fan preset (read) | `STATE`, `*_TIMER` | 4609, 4612–4614 | `profile` | fan | 🟡 |
| fan preset home, away, boost, fireplace | `STATE`, `*_TIMER`, `*_TIME` | 4609, 4612–4614, 20544, 20545 | `async_set_profile` | fan | ✅ |
| fan preset extra | `EXTRA_TIMER`, `EXTRA_TIME` | 4614, 20496 | `async_set_profile(Profile.EXTRA)` | not selectable; shown while active | ⚠️ unit kept its mode |
| fan preset auto | `STATE` = 2, `*_TIMER` = 0 | 4609, 4612–4614 | `async_set_profile(Profile.AUTOMATIC)` | fan | ✅ |
| fan percentage, attributes `fan_speed_*` | `*_SPEED_SETTING` | 20501, 20507, 20513 | `settings.*_fan_speed`, `async_set_*_fan_speed` | fan | ✅ |
| sensor `extract_air` | `TEMP_EXTRACT_AIR` | 4354 | `measurements.extract_air_temperature` | sensor | 🟡 |
| sensor `exhaust_air` | `TEMP_EXHAUST_AIR` | 4355 | `measurements.exhaust_air_temperature` | sensor | 🟡 |
| sensor `outdoor_air` | `TEMP_OUTDOOR_AIR` | 4356 | `measurements.outdoor_air_temperature` | sensor | 🟡 |
| sensor `supply_cell_air` | `TEMP_SUPPLY_CELL_AIR` | 4357 | `measurements.supply_cell_air_temperature` | sensor | 🟡 |
| sensor `supply_air` | `TEMP_SUPPLY_AIR` | 4358 | `measurements.supply_air_temperature` | sensor | 🟡 |
| sensor `optional_air` | `TEMP_OPTIONAL` | 4389 | `sensors.optional_temperature` | sensor, disabled | 🟡 |
| sensor `humidity` | `RH_VALUE` | 4363 | `measurements.humidity` | sensor | 🟡 |
| sensor `co2` | `CO2_VALUE` | 4364 | `measurements.co2` | sensor, disabled | 🟡 |
| sensor `efficiency` | `EXTRACT_EFFICIENCY` | 32776 | — | — | ⛔ not in manual |
| sensor `current_profile` | derived | 4609, 4612–4614 | `profile` | sensor | 🟡 |
| sensor `fan_speed` | `FAN_SPEED`, `MODE` | 4353, 4610 | `measurements.fan_speed` | sensor | 🟡 |
| sensor `extract_fan_speed` | `EXTR_FAN_SPEED` | 4361 | `measurements.extract_fan_rpm` | sensor, disabled | 🟡 |
| sensor `supply_fan_speed` | `SUPP_FAN_SPEED` | 4362 | `measurements.supply_fan_rpm` | sensor, disabled | 🟡 |
| sensor `remaining_time_for_filter` | `FILTER_CHANGED_*`, `FILTER_CHANGE_INTERVAL` | 20546–20548, 20537 | `next_filter_change_date` | sensor | 🟡 read not validated |
| sensor `cell_state` | `CELL_STATE` | 4616 | `runtime.heat_exchanger_state` | sensor | 🟡 |
| sensor `profile_duration` | `*_TIMER`, `*_TIMER_ENABLED` | 4612–4614, 21766, 21767, 21772 | `remaining_profile_duration` | sensor | 🟡 read not validated |
| binary_sensor `post_heater` | `IO_HEATER` | 4868 | — | — | ⛔ not in manual |
| number `supply_air_target_home` | `HOME_AIR_TEMP_TARGET` | 20508 | `async_set_home_air_temperature_target` | number | ✅ |
| number `supply_air_target_away` | `AWAY_AIR_TEMP_TARGET` | 20502 | `async_set_away_air_temperature_target` | number | ✅ |
| number `supply_air_target_boost` | `BOOST_AIR_TEMP_TARGET` | 20514 | `async_set_boost_air_temperature_target` | number | ✅ |
| switch `bypass_locked` | `BYPASS_LOCKED` | 20552 | `async_set_bypass_locked` | — (left out in v1) | ⚠️ |
| date `filter_change_date` | `FILTER_CHANGED_*` | 20546–20548 | read only, no write | — | ⛔ |
| actions `set_profile_fan_speed_*`, `set_profile` | — | — | setters, `async_set_profile` | — (not in v1) | — |

Entities not in core `vallox`:

| Entity (key) | `A_CYC_*` | Register | `vallox-modbus` | Status |
| --- | --- | --- | --- | --- |
| sensor `filter_remaining` | `REMAINING_TIME_FOR_FILTER` | 4620 | `runtime.filter_remaining` | 🟡 |
| binary_sensor `defrosting` | `DEFROSTING` | 4611 | `runtime.defrosting` | 🟡 |
| binary_sensor `fault` | `LIMP_MODE` | 4621 | `runtime.fault` | 🟡 |
| number `fan_speed_home`, `fan_speed_away`, `fan_speed_boost` | `*_SPEED_SETTING` | 20507, 20501, 20513 | `async_set_*_fan_speed` | ✅ |
| number `supply_air_target_extra` (disabled) | `EXTRA_AIR_TEMP_TARGET` | 20493 | `async_set_extra_air_temperature_target` | ✅ |
| number `extra_extract_fan`, `extra_supply_fan` (disabled) | `EXTRA_EXTR_FAN`, `EXTRA_SUPP_FAN` | 20494, 20495 | `async_set_extra_*_fan` | ✅ |
| number `boost_duration`, `fireplace_duration`, `extra_duration` (disabled) | `BOOST_TIME`, `FIREPLACE_TIME`, `EXTRA_TIME` | 20544, 20545, 20496 | `async_set_*_duration` | ✅ |

The remaining registers (Modbus and installation configuration, RH, CO2 and
VOC sensor arrays, raw input values) are only included in the diagnostics.

## Open library work

- Hardware validation of `async_set_profile` for Extra and with an explicit
  duration, the timer switch writes, the Boost and Extra timer switch reads,
  and the filter change date reads.
- Filter change date write, for the core `filter_change_date` date entity.
- Bypass lock write validation, for the core `bypass_locked` switch.
- A hardware read test of the undocumented identity, efficiency (32776) and
  post-heater (4868) registers.
