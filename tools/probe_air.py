"""Read model-specific properties without installing Home Assistant or writing settings."""

import argparse
import importlib.util
import json
from getpass import getpass
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host")
    parser.add_argument("model", choices=["xiaomi.airp.mc6", "zhimi.humidifier.ca6"])
    args = parser.parse_args()
    module_path = (
        Path(__file__).resolve().parents[1]
        / "custom_components/xiaomi_miio/air_devices.py"
    )
    spec = importlib.util.spec_from_file_location("air_devices", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    token = getpass("Device token (hidden): ").strip()
    if len(token) != 32 or any(c not in "0123456789abcdefABCDEF" for c in token):
        raise SystemExit("Expected a 32-character hexadecimal token")
    device = module.AirDevice(args.host, token, model=args.model)
    info = device.info()
    if info.model != args.model:
        raise SystemExit(
            f"Model mismatch: received {info.model}; no properties queried"
        )
    print(
        json.dumps(
            {
                "model": info.model,
                "firmware": info.firmware_version,
                "properties": device.status(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
