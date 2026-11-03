"""Entities for the two additional air devices, isolated from legacy handlers."""

from typing import ClassVar

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.components.humidifier import (
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.components.number import NumberEntity
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_MODEL, UnitOfTemperature, UnitOfTime
from homeassistant.exceptions import HomeAssistantError
from miio import DeviceException

from .air_devices import AIR_MODELS, BOOL_WRITES, CA6, MC6, MODES
from .entity import XiaomiCoordinatedMiioEntity


class AirEntity(XiaomiCoordinatedMiioEntity):
    """Read coordinator state directly and refresh after acknowledged writes."""

    _attr_name = None

    def __init__(self, entry, key=None, name=None):
        super().__init__(
            entry.runtime_data.device,
            entry,
            f"{key}_{entry.unique_id}" if key else entry.unique_id,
            entry.runtime_data.device_coordinator,
        )
        self.key = key
        self._attr_name = name

    def value(self, key):
        return self.coordinator.data.get(key)

    async def write(self, key, value):
        try:
            await self.hass.async_add_executor_job(self._device.write, key, value)
        except (DeviceException, ValueError) as err:
            raise HomeAssistantError(f"Unable to set {key}: {err}") from err
        await self.coordinator.async_request_refresh()

    @property
    def available(self):
        return super().available and (
            self.key is None or self.value(self.key) is not None
        )

    @property
    def is_on(self):
        return self.value("power")

    async def async_turn_on(self, **kwargs):
        await self.write("power", True)

    async def async_turn_off(self, **kwargs):
        await self.write("power", False)


class AirPurifier6Plus(AirEntity, FanEntity):
    """MC6 presets, without interpreting its mode 6 as a selectable preset."""

    _attr_supported_features = (
        FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.PRESET_MODE
    )
    _attr_preset_modes: ClassVar[list[str]] = list(MODES[MC6])

    @property
    def preset_mode(self):
        return next(
            (name for name, value in MODES[MC6].items() if value == self.value("mode")),
            None,
        )

    async def async_set_preset_mode(self, preset_mode):
        if preset_mode not in MODES[MC6]:
            raise HomeAssistantError("Unsupported purifier mode")
        await self.write("mode", MODES[MC6][preset_mode])

    async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs):
        if percentage is not None:
            raise HomeAssistantError("Use presets or the Favorite level control")
        if preset_mode is not None and preset_mode not in MODES[MC6]:
            raise HomeAssistantError("Unsupported purifier mode")
        await self.write("power", True)
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)


class SmartmiHumidifier3(AirEntity, HumidifierEntity):
    """CA6 modes and integer target humidity from 30 to 60 percent."""

    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER
    _attr_supported_features = HumidifierEntityFeature.MODES
    _attr_available_modes: ClassVar[list[str]] = list(MODES[CA6])
    _attr_min_humidity = 30
    _attr_max_humidity = 60

    @property
    def current_humidity(self):
        return self.value("humidity")

    @property
    def target_humidity(self):
        return self.value("target_humidity")

    @property
    def mode(self):
        return next(
            (name for name, value in MODES[CA6].items() if value == self.value("mode")),
            None,
        )

    async def async_set_mode(self, mode):
        if mode not in MODES[CA6]:
            raise HomeAssistantError("Unsupported humidifier mode")
        await self.write("mode", MODES[CA6][mode])

    async def async_set_humidity(self, humidity):
        await self.write("target_humidity", humidity)
        if self.value("mode") != MODES[CA6]["Auto"]:
            await self.async_set_mode("Auto")


# Sensor metadata is explicit: CA6 water levels are categories, not percentages.
SENSORS = {
    "temperature": (
        "Temperature",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
    ),
    "humidity": ("Humidity", "%", SensorDeviceClass.HUMIDITY),
    "pm25": ("PM2.5", "µg/m³", SensorDeviceClass.PM25),
    "pm1": ("PM1", "µg/m³", SensorDeviceClass.PM1),
    "filter_life": ("Filter life", "%", None),
    "filter_time_left": (
        "Filter time left",
        UnitOfTime.HOURS,
        SensorDeviceClass.DURATION,
    ),
    "filter_hours_used": (
        "Filter hours used",
        UnitOfTime.HOURS,
        SensorDeviceClass.DURATION,
    ),
    "actual_speed": ("Motor speed", "rpm", None),
    "fault": ("Fault code", None, None),
    "water_level": ("Water level", None, SensorDeviceClass.ENUM),
    "operating_status": ("Operating status", None, SensorDeviceClass.ENUM),
}
ENUM_SENSORS = {
    "water_level": {0: "empty", 1: "normal", 2: "full"},
    "operating_status": {1: "off", 2: "humidifying", 3: "drying", 4: "cleaning"},
}


class AirSensor(AirEntity, SensorEntity):
    def __init__(self, entry, key):
        name, unit, device_class = SENSORS[key]
        super().__init__(entry, key, name)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        if key in ENUM_SENSORS:
            self._attr_options = list(ENUM_SENSORS[key].values())
        elif unit is not None:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        value = self.value(self.key)
        return ENUM_SENSORS[self.key].get(value) if self.key in ENUM_SENSORS else value


class AirSwitch(AirEntity, SwitchEntity):
    @property
    def is_on(self):
        return self.value(self.key)

    async def async_turn_on(self, **kwargs):
        await self.write(self.key, True)

    async def async_turn_off(self, **kwargs):
        await self.write(self.key, False)


class FavoriteLevel(AirEntity, NumberEntity):
    _attr_native_min_value = 0
    _attr_native_max_value = 9
    _attr_native_step = 1

    async def async_set_native_value(self, value):
        await self.write("favorite_level", value)

    @property
    def native_value(self):
        return self.value("favorite_level")


def setup_air_entities(platform, entry, async_add_entities):
    """Return whether this entry uses the new model-specific platforms."""
    model = entry.data[CONF_MODEL]
    if model not in AIR_MODELS:
        return False
    entities = []
    if platform == "fan" and model == MC6:
        entities = [AirPurifier6Plus(entry)]
    elif platform == "humidifier" and model == CA6:
        entities = [SmartmiHumidifier3(entry)]
    elif platform == "sensor":
        entities = [
            AirSensor(entry, key)
            for key in SENSORS
            if key in entry.runtime_data.device.mapping
        ]
    elif platform == "switch":
        names = {
            "anion": "Ionizer",
            "uv": "UV",
            "screen": "Screen",
            "buzzer": "Buzzer",
            "child_lock": "Child lock",
            "dry": "Automatic drying",
        }
        entities = [
            AirSwitch(entry, key, names[key])
            for key in sorted(BOOL_WRITES[model] - {"power"})
        ]
    elif platform == "number" and model == MC6:
        entities = [FavoriteLevel(entry, "favorite_level", "Favorite level")]
    async_add_entities(entities)
    return True
