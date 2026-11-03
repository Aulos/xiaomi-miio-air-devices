"""Exercise new platforms against real HA 2026.10.4 entities/coordinators."""

import importlib
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from miio import DeviceException

from custom_components.xiaomi_miio import get_platforms
from custom_components.xiaomi_miio.air_devices import CA6, MC6, AirDevice
from custom_components.xiaomi_miio.air_entities import (
    AirPurifier6Plus,
    AirSensor,
    SmartmiHumidifier3,
    setup_air_entities,
)
from custom_components.xiaomi_miio.const import CONF_FLOW_TYPE, MODELS_ALL


@pytest.fixture
async def environment(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    coordinator = DataUpdateCoordinator(
        hass, logging.getLogger(__name__), name="test", config_entry=None
    )
    coordinator.async_set_updated_data(
        {
            "power": True,
            "mode": 0,
            "humidity": 45,
            "target_humidity": 50,
            "water_level": 1,
        }
    )
    coordinator.async_request_refresh = AsyncMock()

    def entry(model):
        return SimpleNamespace(
            data={"model": model, "mac": None, CONF_FLOW_TYPE: "device"},
            title="Test air device",
            unique_id="test-air-device",
            runtime_data=SimpleNamespace(
                device=AirDevice("192.0.2.1", "0" * 32, model=model),
                device_coordinator=coordinator,
            ),
        )

    yield hass, coordinator, entry
    await hass.async_stop()


@pytest.mark.asyncio
async def test_all_platforms_dispatch_new_models(environment):
    hass, _coordinator, entry = environment
    for model in (MC6, CA6):
        assert model in MODELS_ALL
        config_entry = entry(model)
        collected = []
        for platform in get_platforms(config_entry):
            module = importlib.import_module(
                "custom_components.xiaomi_miio." + platform
            )
            await module.async_setup_entry(hass, config_entry, collected.extend)
        assert any(
            isinstance(e, AirPurifier6Plus if model == MC6 else SmartmiHumidifier3)
            for e in collected
        )
        assert len({e.unique_id for e in collected}) == len(collected)
        for entity in collected:
            entity.hass = hass
            assert entity.device_info["model"] == model
            # Exercise HA's state properties, including missing optional readings.
            _ = entity.available
            _ = entity.state
            _ = entity.capability_attributes


@pytest.mark.asyncio
async def test_unknown_mode_is_unknown_not_auto(environment):
    _hass, coordinator, entry = environment
    purifier = AirPurifier6Plus(entry(MC6))
    coordinator.data["mode"] = 6
    assert purifier.preset_mode is None
    coordinator.data["mode"] = 99
    assert purifier.preset_mode is None


@pytest.mark.asyncio
async def test_humidity_setter_writes_target_then_auto(environment):
    hass, coordinator, entry = environment
    humidifier = SmartmiHumidifier3(entry(CA6))
    humidifier.hass = hass
    humidifier._device.write = Mock()
    await humidifier.async_set_humidity(45.0)
    assert humidifier._device.write.call_args_list[0].args == ("target_humidity", 45.0)
    assert humidifier._device.write.call_args_list[1].args == ("mode", 1)
    assert coordinator.async_request_refresh.await_count == 2


@pytest.mark.asyncio
async def test_failed_target_does_not_change_mode_or_state(environment):
    hass, coordinator, entry = environment
    humidifier = SmartmiHumidifier3(entry(CA6))
    humidifier.hass = hass
    humidifier._device.write = Mock(side_effect=DeviceException("rejected"))
    with pytest.raises(HomeAssistantError):
        await humidifier.async_set_humidity(45)
    humidifier._device.write.assert_called_once_with("target_humidity", 45)
    assert humidifier.target_humidity == 50
    coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_water_level_is_categorical(environment):
    _hass, coordinator, entry = environment
    sensor = AirSensor(entry(CA6), "water_level")
    assert sensor.native_value == "normal"
    assert sensor.native_unit_of_measurement is None
    coordinator.data["water_level"] = 127
    assert sensor.native_value is None


def test_legacy_model_keeps_original_path():
    add = Mock()
    entry = SimpleNamespace(data={"model": "zhimi.humidifier.ca4"})
    assert setup_air_entities("humidifier", entry, add) is False
    add.assert_not_called()
