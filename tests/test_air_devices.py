"""Check protocol contracts against published schemas and recorded LAN replies."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from miio import DeviceException

from custom_components.xiaomi_miio.air_devices import (
    ACTIONS,
    BOOL_WRITES,
    CA6,
    COUNTRY_CODES,
    MAPPINGS,
    MC6,
    MODES,
    RANGES,
    WRITE_ONLY,
    AirDevice,
)


@pytest.mark.parametrize(
    "model,filename",
    [(MC6, "xiaomi-airp-mc6-spec.json"), (CA6, "zhimi-humidifier-ca6-spec.json")],
)
def test_mapping_matches_primary_schema(model, filename):
    spec = json.loads((Path(__file__).parents[1] / filename).read_text())
    props = {
        (s["iid"], p["iid"]): p
        for s in spec["services"]
        for p in s.get("properties", [])
    }
    for key, pair in MAPPINGS[model].items():
        assert "read" in props[pair]["access"], key
    for key in BOOL_WRITES[model] | set(RANGES[model]) | {"mode"}:
        pair = {**MAPPINGS[model], **WRITE_ONLY[model]}[key]
        assert "write" in props[pair]["access"], key
    assert set(MODES[model].values()) <= {
        v["value"] for v in props[MAPPINGS[model]["mode"]]["value-list"]
    }


def make_device(model=MC6):
    return AirDevice("192.0.2.1", "0" * 32, model=model)


def test_recorded_reads_and_failed_optional_property():
    device = make_device()
    device.get_properties_for_mapping = Mock(
        return_value=[
            {"did": "power", "siid": 2, "piid": 1, "code": 0, "value": True},
            {"did": "mode", "siid": 2, "piid": 3, "code": 0, "value": 0},
            {"did": "pm25", "siid": 3, "piid": 4, "code": 0, "value": 2},
            {"did": "temperature", "siid": 3, "piid": 2, "code": -4004},
        ]
    )
    result = device.status()
    assert result["power"] is True
    assert result["mode"] == 0
    assert result["pm25"] == 2
    assert result["temperature"] is None
    assert result["humidity"] is None


def test_missing_power_fails_poll():
    device = make_device()
    device.get_properties_for_mapping = Mock(return_value=[])
    with pytest.raises(DeviceException):
        device.status()


@pytest.mark.parametrize(
    "model,mode,value",
    [(MC6, "Sleep", 3), (MC6, "Favorite", 5), (CA6, "Auto", 1), (CA6, "Favorite", 0)],
)
def test_modes_use_model_specific_wire_values(model, mode, value):
    device = make_device(model)
    pair = device.mapping["mode"]
    device.send = Mock(return_value=[{**pair, "code": 0}])
    device.write("mode", MODES[model][mode])
    device.send.assert_called_once_with(
        "set_properties", [{"did": "mode", **pair, "value": value}]
    )


@pytest.mark.parametrize("value", [30.0, 45.0, 60.0])
def test_humidity_uses_integer_encoding(value):
    device = make_device(CA6)
    device.send = Mock(return_value=[{"siid": 2, "piid": 6, "code": 0}])
    device.write("target_humidity", value)
    sent = device.send.call_args.args[1][0]["value"]
    assert type(sent) is int and sent == value


@pytest.mark.parametrize(
    "key,value",
    [
        ("target_humidity", 29),
        ("target_humidity", 61),
        ("target_humidity", 45.5),
        ("target_humidity", float("nan")),
        ("power", 1),
        ("mode", 3),
        ("fault", 0),
    ],
)
def test_invalid_writes_never_reach_device(key, value):
    device = make_device(CA6)
    device.send = Mock()
    with pytest.raises(ValueError):
        device.write(key, value)
    device.send.assert_not_called()


@pytest.mark.parametrize(
    "reply",
    [
        [],
        None,
        [{"siid": 2, "piid": 1, "code": -4004}],
        [{"siid": 2, "piid": 5, "code": 0}],
    ],
)
def test_rejected_or_mismatched_write_is_not_success(reply):
    device = make_device()
    device.send = Mock(return_value=reply)
    with pytest.raises(DeviceException):
        device.write("power", True)


def test_extended_mc6_schema():
    spec = json.loads(
        (Path(__file__).parents[1] / "xiaomi-airp-mc6-spec.json").read_text()
    )
    properties = {
        (s["iid"], p["iid"]): p
        for s in spec["services"]
        for p in s.get("properties", [])
    }
    actions = {
        (s["iid"], a["iid"]): a for s in spec["services"] for a in s.get("actions", [])
    }
    for key, pair in WRITE_ONLY[MC6].items():
        assert properties[pair]["access"] == ["write"]
        assert tuple(properties[pair]["value-range"][:2]) == RANGES[MC6][key]
    assert set(COUNTRY_CODES) == {
        v["value"] for v in properties[(13, 11)]["value-list"]
    }
    for pair in ACTIONS.values():
        assert actions[pair]["in"] == []


def test_read_poll_does_not_query_write_only_counters():
    device = make_device()

    def reply(method, params):
        assert method == "get_properties"
        assert not any(p["siid"] == 10 for p in params)
        return [
            {**p, "code": 0, "value": True if p["did"] == "power" else 0}
            for p in params
        ]

    device.send = Mock(side_effect=reply)
    assert device.status()["power"] is True


@pytest.mark.parametrize(
    "key,value,pair",
    [
        ("filter_debug_used_time", 12.0, (10, 1)),
        ("filter_debug_used_life", 50, (10, 2)),
        ("update_heartbeat", 30, (12, 1)),
        ("country_code", 2, (13, 11)),
    ],
)
def test_extended_write_encoding(key, value, pair):
    device = make_device()
    device.send = Mock(return_value=[{"siid": pair[0], "piid": pair[1], "code": 0}])
    device.write(key, value)
    device.send.assert_called_once_with(
        "set_properties",
        [{"did": key, "siid": pair[0], "piid": pair[1], "value": int(value)}],
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("country_code", 0),
        ("country_code", True),
        ("filter_debug_used_life", 101),
        ("update_heartbeat", -1),
    ],
)
def test_extended_invalid_writes(key, value):
    device = make_device()
    device.send = Mock()
    with pytest.raises(ValueError):
        device.write(key, value)
    device.send.assert_not_called()


@pytest.mark.parametrize("key,pair", list(ACTIONS.items()))
def test_action_wire_contract(key, pair):
    device = make_device()
    device.send = Mock(
        return_value={"siid": pair[0], "aiid": pair[1], "code": 0, "out": []}
    )
    device.perform_action(key)
    device.send.assert_called_once_with(
        "action", {"did": key, "siid": pair[0], "aiid": pair[1], "in": []}
    )


@pytest.mark.parametrize(
    "reply", [None, [], {"code": -1}, {"code": 0, "siid": 13, "aiid": 1}]
)
def test_action_failure_is_not_success(reply):
    device = make_device()
    device.send = Mock(return_value=reply)
    with pytest.raises(DeviceException):
        device.perform_action("reset_filter")


def test_actions_not_available_on_ca6():
    device = make_device(CA6)
    device.send = Mock()
    with pytest.raises(ValueError):
        device.perform_action("reset_filter")
    device.send.assert_not_called()
