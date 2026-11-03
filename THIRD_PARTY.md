# Sources and licenses

The copied Home Assistant integration and translations are from Core 2026.10.4, licensed under Apache License 2.0. Original headers are retained. Local changes register MC6/CA6, dispatch them to the added modules and set a custom integration version. Original license: `licenses/home-assistant-Apache-2.0.txt`.

- https://github.com/home-assistant/core/tree/2026.10.4/homeassistant/components/xiaomi_miio

The CA6 mapping and target-humidity integer encoding in `air_devices.py` are adapted from python-miio's CA6 implementation, licensed under GPL-3.0. `air_devices.py` is provided under GPL-3.0; see `licenses/python-miio-GPL-3.0.txt`. The full source is included. No python-miio package files are replaced.

- https://github.com/rytilahti/python-miio/pull/1885
- https://github.com/rytilahti/python-miio/blob/master/miio/integrations/zhimi/humidifier/airhumidifier_miot.py

The other new files and modifications are provided under Apache License 2.0. The distribution retains each component's licensing.

The model specifications are included as reference data from the public MIoT specification service:

- https://miot-spec.org/miot-spec-v2/instance?type=urn:miot-spec-v2:device:air-purifier:0000A007:xiaomi-mc6:1:0000D050
- https://miot-spec.org/miot-spec-v2/instance?type=urn:miot-spec-v2:device:humidifier:0000A00E:zhimi-ca6:1

The Xiaomi icon is from https://github.com/home-assistant/brands/tree/master/core_integrations/xiaomi_miio and identifies the device integration. Xiaomi trademarks belong to their owner. This project is not affiliated with Xiaomi or Home Assistant.
