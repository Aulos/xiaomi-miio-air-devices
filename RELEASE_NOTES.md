Initial experimental release for Home Assistant 2026.10.4.

Adds Xiaomi Air Purifier 6 Plus (xiaomi.airp.mc6) and Smartmi Humidifier 3 (zhimi.humidifier.ca6). Includes manual token setup, local MIoT polling and controls, and HACS metadata. The pinned python-miio dependency is unchanged.

32 automated tests pass against HA 2026.10.4. Purifier power, mode and PM2.5 reads have hardware confirmation. Other readings, writes and humidifier operation still require hardware validation.

This overrides built-in xiaomi_miio for all entries. Back up first; check compatibility before HA upgrades. See README for installation and rollback.
