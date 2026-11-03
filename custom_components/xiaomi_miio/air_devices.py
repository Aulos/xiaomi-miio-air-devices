"""MC6 and CA6 mappings using the integration's pinned python-miio transport.

CA6 mapping adapted from python-miio's airhumidifier_miot implementation.
See THIRD_PARTY.md for sources and licensing.
"""

from miio import DeviceException, MiotDevice

MC6 = "xiaomi.airp.mc6"
CA6 = "zhimi.humidifier.ca6"
AIR_MODELS = (MC6, CA6)

MAPPINGS = {
    MC6: {
        "power": (2, 1),
        "fault": (2, 2),
        "mode": (2, 3),
        "fan_level": (2, 4),
        "anion": (2, 5),
        "uv": (2, 6),
        "humidity": (3, 1),
        "temperature": (3, 2),
        "pm25": (3, 4),
        "pm10": (3, 5),
        "pm1": (3, 9),
        "filter_life": (4, 1),
        "filter_time_left": (4, 2),
        "filter_hours_used": (4, 3),
        "screen": (6, 1),
        "brightness": (6, 2),
        "buzzer": (7, 1),
        "child_lock": (8, 1),
        "favorite_level": (9, 1),
        "air_quality": (3, 3),
        "update_heartbeat": (12, 1),
        "favorite_square": (13, 1),
        "reboot_cause": (13, 2),
        "motor_rpm_set": (13, 3),
        "motor_rpm_feedback": (13, 4),
        "iic_error_count": (13, 6),
        "common_property": (13, 8),
        "country_code": (13, 11),
    },
    CA6: {
        "power": (2, 1),
        "fault": (2, 2),
        "mode": (2, 5),
        "target_humidity": (2, 6),
        "water_level": (2, 7),
        "dry": (2, 8),
        "operating_status": (2, 9),
        "temperature": (3, 7),
        "humidity": (3, 9),
        "buzzer": (4, 1),
        "brightness": (5, 2),
        "child_lock": (6, 1),
        "actual_speed": (7, 1),
    },
}
MODES = {
    MC6: {"Auto": 0, "Sleep": 3, "Favorite": 5},
    CA6: {"Favorite": 0, "Auto": 1, "Sleep": 2},
}
BOOL_WRITES = {
    MC6: {"power", "anion", "uv", "screen", "buzzer", "child_lock"},
    CA6: {"power", "dry", "buzzer", "child_lock"},
}
RANGES = {
    MC6: {
        "fan_level": (0, 2),
        "brightness": (0, 2),
        "favorite_level": (0, 9),
        "update_heartbeat": (0, 65535),
        "filter_debug_used_time": (0, 10000),
        "filter_debug_used_life": (0, 100),
    },
    CA6: {"brightness": (0, 2), "target_humidity": (30, 60)},
}


WRITE_ONLY = {
    MC6: {"filter_debug_used_time": (10, 1), "filter_debug_used_life": (10, 2)},
    CA6: {},
}
COUNTRY_CODES = {
    2: "EU",
    1: "US",
    82: "KR",
    886: "TW",
    66: "TH",
    44: "UK",
    91: "IN",
    86: "CN",
    81: "JP",
}
ACTIONS = {
    "toggle": (2, 1),
    "reset_filter": (4, 1),
    "toggle_mode": (13, 1),
    "toggle_fan_level": (13, 2),
}


class AirDevice(MiotDevice):
    """Small release-compatible adapter; never falls back to another model."""

    def __init__(self, ip, token, *, model, **kwargs):
        if model not in AIR_MODELS:
            raise ValueError(f"Unsupported air device: {model}")
        self.air_model = model
        mapping = {
            key: {"siid": pair[0], "piid": pair[1]}
            for key, pair in MAPPINGS[model].items()
        }
        super().__init__(ip, token, model=model, mapping=mapping, **kwargs)

    def status(self):
        """Missing/failed optional properties become unknown, never stale values."""
        values = dict.fromkeys(self.mapping)
        by_pair = {(p["siid"], p["piid"]): key for key, p in self.mapping.items()}
        response = self.get_properties_for_mapping(max_properties=5)
        if not isinstance(response, list):
            raise DeviceException("Invalid MIoT property response")
        for item in response:
            if not isinstance(item, dict):
                continue
            key = by_pair.get((item.get("siid"), item.get("piid")))
            if key and item.get("code") == 0:
                values[key] = item.get("value")
        if type(values["power"]) is not bool:
            raise DeviceException("MIoT power property unavailable")
        return values

    def write(self, key, value):
        """Validate schema values and require a successful per-property reply."""
        model = self.air_model
        if key in BOOL_WRITES[model]:
            valid = type(value) is bool
        elif model == MC6 and key == "country_code":
            valid = type(value) is int and value in COUNTRY_CODES
        elif key == "mode":
            valid = type(value) is int and value in MODES[model].values()
        elif key in RANGES[model]:
            low, high = RANGES[model][key]
            valid = (
                not isinstance(value, bool)
                and isinstance(value, (int, float))
                and low <= value <= high
                and value == int(value)
            )
            if valid:
                value = int(value)
        else:
            valid = False
        if not valid:
            raise ValueError(f"Invalid value for {model} property {key}")
        if key in WRITE_ONLY[model]:
            siid, piid = WRITE_ONLY[model][key]
            prop = {"siid": siid, "piid": piid}
            result = self.send("set_properties", [{"did": key, **prop, "value": value}])
        else:
            prop = self.mapping[key]
            result = self.set_property(key, value)
        if (
            not isinstance(result, list)
            or len(result) != 1
            or not isinstance(result[0], dict)
            or result[0].get("code") != 0
            or result[0].get("siid") != prop["siid"]
            or result[0].get("piid") != prop["piid"]
        ):
            raise DeviceException(f"MIoT rejected property {key}")
        return result

    def perform_action(self, key):
        """Only explicitly exposed no-argument MC6 actions are permitted."""
        if self.air_model != MC6 or key not in ACTIONS:
            raise ValueError(f"Unsupported action: {key}")
        siid, aiid = ACTIONS[key]
        result = self.send("action", {"did": key, "siid": siid, "aiid": aiid, "in": []})
        if (
            not isinstance(result, dict)
            or result.get("code") != 0
            or result.get("siid") != siid
            or result.get("aiid") != aiid
        ):
            raise DeviceException(f"MIoT rejected action {key}")
        return result
