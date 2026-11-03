# Validation results

- 32 tests passed against Home Assistant 2026.10.4 / Python 3.14 and python-miio 0.5.12.
- Tests mock transport; no commands were sent to real devices during this build.
- New modules, tests and probe pass Ruff. All integration Python files compile.
- Existing upstream device_tracker.py triggers a Ruff F821 forward-annotation diagnostic; that unchanged module is outside this patch.
- Runtime imports of the config flow and all affected platforms passed.
- Preserved the pinned dependencies and existing model routes.
- Existing upstream dependencies emit deprecation warnings.
- Live HA OS installation, legacy hardware regression, new-model writes and humidifier reads remain unverified.
