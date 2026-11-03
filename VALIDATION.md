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
