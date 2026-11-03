"""Exercise new platforms against real HA 2026.10.4 entities/coordinators."""

import importlib
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from miio import DeviceException

from custom_components.xiaomi_miio import get_platforms
from custom_components.xiaomi_miio.air_devices import CA6, MC6, AirDevice
from custom_components.xiaomi_miio.air_entities import (
    AdvancedNumber,
    AirButton,
    AirPurifier6Plus,
    AirSelect,
    AirSensor,
    FavoriteLevel,
    SmartmiHumidifier3,
    setup_air_entities,
)
from custom_components.xiaomi_miio.const import CONF_FLOW_TYPE, MODELS_ALL


@pytest.fixture
async def environment(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    dr.async_setup(hass)
    await dr.async_load(hass, load_empty=True)
    await er.async_load(hass, load_empty=True)
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


@pytest.mark.asyncio
async def test_favorite_level_exposes_rpm_options(environment):
    hass, coordinator, entry = environment
    level = FavoriteLevel(entry(MC6), "favorite_level", "Favorite level")
    level.hass = hass
    coordinator.data.update(mode=5, favorite_level=9)
    assert level.available
    assert level.state == "Level 9 — 1530 RPM"
    coordinator.data["favorite_level"] = 0
    assert level.available
    assert level.state == "Level 0 — 400 RPM"
    coordinator.data["favorite_level"] = None
    assert not level.available


@pytest.mark.asyncio
async def test_extended_entities_defaults_and_states(environment):
    hass, coordinator, entry = environment
    from homeassistant.const import EntityCategory

    coordinator.data.update(
        air_quality=0, motor_rpm_feedback=450, common_property="x" * 300
    )
    sensor = AirSensor(entry(MC6), "air_quality")
    assert sensor.native_value == "excellent"
    diagnostic = AirSensor(entry(MC6), "motor_rpm_feedback")
    assert diagnostic.native_value == 450
    assert diagnostic.entity_category == EntityCategory.DIAGNOSTIC
    assert not diagnostic.entity_registry_enabled_default
    raw = AirSensor(entry(MC6), "common_property")
    assert len(raw.native_value) == 255
    assert raw.extra_state_attributes == {"raw_value": "x" * 300}
    debug = AdvancedNumber(entry(MC6), "filter_debug_used_life", "Debug")
    debug.hass = hass
    assert debug.available
    assert debug.native_value is None
    assert debug.state is None
    assert not debug.entity_registry_enabled_default


@pytest.mark.asyncio
async def test_brightness_and_action_commands(environment):
    hass, coordinator, entry = environment
    config = entry(MC6)
    config.runtime_data.device.write = Mock()
    config.runtime_data.device.perform_action = Mock()
    select = AirSelect(
        config, "brightness", "Brightness", {0: "Dim", 1: "On", 2: "Mid"}
    )
    select.hass = hass
    coordinator.data["brightness"] = 2
    assert select.current_option == "Mid"
    await select.async_select_option("Dim")
    config.runtime_data.device.write.assert_called_once_with("brightness", 0)
    with pytest.raises(HomeAssistantError):
        await select.async_select_option("Invalid")
    button = AirButton(config, "reset_filter", "Reset")
    button.hass = hass
    assert button.available
    assert not button.entity_registry_enabled_default
    await button.async_press()
    config.runtime_data.device.perform_action.assert_called_once_with("reset_filter")
    config.runtime_data.device.perform_action.side_effect = DeviceException("rejected")
    with pytest.raises(HomeAssistantError):
        await button.async_press()


@pytest.mark.asyncio
async def test_favorite_dropdown_writes_levels_not_rpms(environment):
    hass, coordinator, entry = environment
    level = FavoriteLevel(entry(MC6))
    level.hass = hass
    level._device.write = Mock()
    for index, rpm in enumerate((400, 480, 650, 700, 800, 930, 1100, 1250, 1370, 1530)):
        option = f"Level {index} — {rpm} RPM"
        assert level.options[index] == option
        await level.async_select_option(option)
        level._device.write.assert_called_with("favorite_level", index)
    assert level._device.write.call_count == 10
    with pytest.raises(HomeAssistantError):
        await level.async_select_option("400")
    coordinator.data["favorite_level"] = 99
    assert level.current_option is None


@pytest.mark.asyncio
async def test_favorite_number_registry_removed_and_select_created(environment):
    from homeassistant.helpers import entity_registry as er

    from custom_components.xiaomi_miio import number, select

    hass, _coordinator, entry = environment
    config = entry(MC6)
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "number", "xiaomi_miio", "favorite_level_test-air-device"
    )
    other = registry.async_get_or_create(
        "number", "xiaomi_miio", "favorite_level_other-device"
    )
    numbers, selects = [], []
    await number.async_setup_entry(hass, config, numbers.extend)
    await select.async_setup_entry(hass, config, selects.extend)
    assert registry.async_get(old.entity_id) is None
    assert registry.async_get(other.entity_id) is not None
    assert not any(e.key == "favorite_level" for e in numbers)
    assert sum(isinstance(e, FavoriteLevel) for e in selects) == 1
