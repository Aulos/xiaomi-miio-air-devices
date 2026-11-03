"""Check protocol contracts against published schemas and recorded LAN replies."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from miio import DeviceException

from custom_components.xiaomi_miio.air_devices import (
    BOOL_WRITES,
    CA6,
    MAPPINGS,
    MC6,
    MODES,
    RANGES,
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
        assert "write" in props[MAPPINGS[model][key]]["access"], key
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
