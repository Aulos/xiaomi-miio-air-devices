# Xiaomi Miio test integration for HA 2026.10.4

Adds `xiaomi.airp.mc6` and `zhimi.humidifier.ca6` to a copy of the built-in Xiaomi Miio integration. This is a local test build, version `2026.10.4.3`, not an upstream release.

The library dependencies remain exactly those of HA 2026.10.4. A small adapter uses python-miio 0.5.12's existing MIoT transport and the two models' property mappings. The CA6 mapping comes from upstream python-miio; MC6 comes from its published MIoT specification. There is no cloud dependency for polling or controlling either new model when configured manually.

## What it exposes

- Purifier: on/off; Auto, Sleep and Favorite presets; favorite level 0–9; temperature, humidity, PM2.5, PM1, filter life, filter hours used, filter time left and fault code; screen, buzzer, child lock, ionizer and UV switches.
- Humidifier: on/off; Favorite, Auto and Sleep modes; integer target humidity 30–60%; current humidity, temperature, water level, operating status, motor speed and fault code; automatic drying, buzzer and child lock switches. Setting target humidity also selects Auto after the target write succeeds.
- Water level is empty/normal/full. It is not a continuous percentage measurement.
- Unsupported optional properties become unavailable or unknown. A failed power read fails the poll. Writes require a successful matching MIoT acknowledgement, then refresh the device state.
- The schema's MC6 mode 6 is not exposed as a selectable preset; an unknown mode is shown as unknown rather than guessed as Auto.

### Additional MC6 entities (2026.10.4.3)

Enabled by default: screen brightness (Dim/On/Mid, following the schema's labels), a separate three-level fan selector, and the air-quality category. Favorite level retains its existing numeric entity and ID.

Disabled by default:
- Diagnostic sensors: motor target/actual RPM, reboot cause, I²C error count, Favorite coverage area (raw string), common property (raw string), and dust (raw value).
- Buttons: reset filter life, toggle power, cycle mode, and cycle fan level.
- Advanced configuration: country code, AQI update heartbeat, and the two write-only filter-debug counters.

To enable one, open Settings → Devices & services → Entities, find the disabled entity for the purifier, open its settings and enable it. Reset filter life only after replacing the filter. Country code and filter-debug controls alter device configuration/history; leave them disabled unless deliberately using them. No action or setting is sent by installation, enabling an entity, or polling.

The new entities are mapped from the published schema; their local behavior still needs hardware validation. Missing/unsupported reads appear unavailable. All readable mapped properties are polled even when their entities are disabled. Write-only debug counters are never polled and remain unknown after writes because no readback is available. The heartbeat's unit is undocumented. Dust has no declared unit and a 0–100 range, so it is not presented as PM10 mass concentration. Raw strings longer than HA's 255-character state limit are shortened in state, with the full value in the `raw_value` attribute. Humidifier cleaning actions remain outside this MC6 update.

New entity labels are in English; the original integration's translations are included.

## Before installation: read-only device check

Unzip the archive on your Mac and open a terminal in the extracted folder. Using the Python environment created earlier:

```sh
/tmp/xiaomi-discovery/bin/python tools/probe_air.py PURIFIER_IP xiaomi.airp.mc6
/tmp/xiaomi-discovery/bin/python tools/probe_air.py HUMIDIFIER_IP zhimi.humidifier.ca6
```

Replace the IP placeholders with current device addresses. Each command prompts for that device's token. Tokens are not saved or printed. The output contains model, firmware and property readings only. These commands do not change device settings. `null` indicates a missing/failed property. Add `--raw` to include per-property MIoT result codes when checking unsupported properties. The probe never invokes actions or writes the filter-debug counters.

## Install with HACS

This is a custom repository, not a listing in the default HACS store.

1. Open HACS → three-dot menu → Custom repositories.
2. Add `https://github.com/Aulos/xiaomi-miio-air-devices` with type **Integration**.
3. Find **Xiaomi Miio Air Devices**, download it and restart Home Assistant.
4. Add each device using **Xiaomi Home → Configure manually**, supplying its IP and token.

**This overrides the built-in `xiaomi_miio` integration for all its entries.** Back up HA first. If another HACS repository manages the same domain, do not install both. Remove this override before upgrading beyond the tested HA version unless a compatible release is available.

[Add repository to HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=Aulos&repository=xiaomi-miio-air-devices&category=integration)

## Manual installation on HA OS

1. Make a Home Assistant backup. If `/config/custom_components/xiaomi_miio` already exists, preserve that folder before proceeding; do not merge two custom implementations.
2. Using your existing Samba, SSH or Studio Code Server access, copy the archive's `custom_components/xiaomi_miio` folder into `/config/custom_components/xiaomi_miio`. The resulting file must be `/config/custom_components/xiaomi_miio/manifest.json`, with version `2026.10.4.3`. Keep `THIRD_PARTY.md` and the licenses with your copy.
3. Restart Home Assistant Core. HA will report that `xiaomi_miio` is a custom integration. This is expected. No pip commands inside the managed Core container are needed.
4. In Settings → Devices & services → Add integration, select **Xiaomi Home**, the integration for domain `xiaomi_miio`. Choose **Configure manually**. Enter the purifier IP and token. Repeat for the humidifier. This avoids the Xiaomi account email-verification problem.
5. Check the new entities and Settings → System → Logs. Compare initial readings with the device display/app before testing controls. Test power and modes one at a time and restore your preferred settings. For the humidifier, use a filled tank and confirm integer targets within 30–60%. Additional sensor and write behavior is still awaiting your hardware validation.

This folder overrides the built-in `xiaomi_miio` integration for **all** its entries, including existing Xiaomi devices. The legacy device handlers and dependencies are retained, but existing devices should be checked after restarting. Standard fan/humidifier/switch/number/select/button entity actions are supported for the new models; legacy `xiaomi_miio` vendor service actions are not wired to the new entities.

## Network access

Allow the Home Assistant host to reach each device over UDP destination port 54321, including return traffic. Some devices only respond to sources on their own subnet. If a same-subnet test succeeds but routed requests fail despite correct firewall rules, a narrow source-NAT rule on the device VLAN can help. Restrict it to the HA source IP, device destination IP and UDP port 54321.

## Roll back and update

Move `/config/custom_components/xiaomi_miio` completely outside `custom_components`, then restart Core. The original built-in integration resumes for supported devices. The two new models will lose support; disable/remove their entries if needed. Do not delete existing Xiaomi configuration entries to roll back this code.

This override does not automatically receive future built-in Xiaomi integration changes. Before upgrading HA beyond 2026.10.4, remove the override or rebase and test it for the new release. The archive contains no credentials and does not alter firmware.

## Validation

Tests run against installed Home Assistant 2026.10.4 and python-miio 0.5.12. They cover manual model detection, device/coordinator dispatch, all relevant platform setup functions, entity states, schema mapping, recorded purifier responses, unknown modes, optional property failures, invalid writes, integer humidity encoding, command rejection and CA4 routing preservation. Network responses are mocked in automated tests; these are not end-to-end tests of a running HA OS instance.

To reproduce locally with Python 3.14 and uv:

```sh
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python 'homeassistant==2026.10.4' 'python-miio==0.5.12' 'construct==2.10.68' 'micloud==0.5' pytest pytest-asyncio
.venv/bin/python -m pytest -q
```

Hardware evidence so far: purifier local reads and routed reads succeeded, the HA device page showed environmental/filter readings, and the user confirmed screen switching physically works. Favorite mode, fan level, and Favorite level reads succeeded; the final four-property batch also succeeded. The 2026.10.4.3 additions, other writes, humidifier operation, and WAN-blocked operation remain unverified on hardware.
