# Validation results

- 32 tests passed against Home Assistant 2026.10.4 / Python 3.14 and python-miio 0.5.12.
- Tests mock transport; no commands were sent to real devices during this build.
- New modules, tests and probe pass Ruff. All integration Python files compile.
- Existing upstream device_tracker.py triggers a Ruff F821 forward-annotation diagnostic; that unchanged module is outside this patch.
- Runtime imports of the config flow and all affected platforms passed.
- Preserved the pinned dependencies and existing model routes.
- Existing upstream dependencies emit deprecation warnings.
- Live HA OS installation, legacy hardware regression, new-model writes and humidifier reads remain unverified.

## 2026.10.4.2

Fixed a shared `value` helper shadowing NumberEntity.value. The regression test checks HA state is numeric for Favorite levels 9 and 0 and unavailable for a missing reading. All 33 tests pass against HA 2026.10.4; Ruff passes on changed Python files. User confirmed individual and batched reads of Favorite level (9/1), code 0, value 9. Hardware verification of the updated UI remains pending.

## 2026.10.4.3

54 tests pass against HA 2026.10.4. Extended tests check schema property/action IDs, write-only exclusion from polling, country/range validation, exact action messages and rejection handling, select commands, diagnostic defaults, raw string state limits, and unavailable/unknown values. Ruff and compilation pass for changed modules. No live commands were sent; added MC6 capabilities are schema-based and await local hardware validation. Existing entity IDs and CA6 behavior are retained.

## 2026.10.4.4

56 tests pass. Favorite is now a select using the ten locally measured target RPMs. Tests verify all labels map to integer level IDs, unknown/missing states, invalid options, and removal of only the device's old Favorite number registry entry. No device commands were sent during this update. UI verification on the user's HA installation remains pending.
