"""Entities for the two additional air devices, isolated from legacy handlers."""

from typing import ClassVar

from homeassistant.components.button import ButtonEntity
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.components.humidifier import (
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.components.number import NumberEntity
from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import (
    CONF_MODEL,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.exceptions import HomeAssistantError
from miio import DeviceException

from .air_devices import (
    AIR_MODELS,
    BOOL_WRITES,
    CA6,
    COUNTRY_CODES,
    MC6,
    MODES,
    RANGES,
    WRITE_ONLY,
)
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

    def reading(self, key):
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
            self.key is None or self.reading(self.key) is not None
        )

    @property
    def is_on(self):
        return self.reading("power")

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
            (
                name
                for name, value in MODES[MC6].items()
                if value == self.reading("mode")
            ),
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
        return self.reading("humidity")

    @property
    def target_humidity(self):
        return self.reading("target_humidity")

    @property
    def mode(self):
        return next(
            (
                name
                for name, value in MODES[CA6].items()
                if value == self.reading("mode")
            ),
            None,
        )

    async def async_set_mode(self, mode):
        if mode not in MODES[CA6]:
            raise HomeAssistantError("Unsupported humidifier mode")
        await self.write("mode", MODES[CA6][mode])

    async def async_set_humidity(self, humidity):
        await self.write("target_humidity", humidity)
        if self.reading("mode") != MODES[CA6]["Auto"]:
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
    "air_quality": ("Air quality", None, SensorDeviceClass.ENUM),
    # The schema declares no unit for 3/5, so do not label it as PM10 mass density.
    "pm10": ("Dust (raw)", None, None),
    "favorite_square": ("Favorite coverage area (raw)", None, None),
    "reboot_cause": ("Reboot cause", None, SensorDeviceClass.ENUM),
    "motor_rpm_set": ("Motor target speed", "rpm", None),
    "motor_rpm_feedback": ("Motor actual speed", "rpm", None),
    "iic_error_count": ("I²C error count", None, None),
    "common_property": ("Common property (raw)", None, None),
}
DIAGNOSTIC_SENSORS = {
    "reboot_cause",
    "motor_rpm_set",
    "motor_rpm_feedback",
    "iic_error_count",
    "common_property",
    "favorite_square",
    "pm10",
}
ENUM_SENSORS = {
    "air_quality": {
        0: "excellent",
        1: "good",
        2: "moderate",
        3: "poor",
        4: "heavy_pollution",
        5: "hazardous",
    },
    "reboot_cause": {
        0: "power",
        1: "external_pin",
        2: "software",
        3: "watchdog",
        4: "unknown",
    },
    "water_level": {0: "empty", 1: "normal", 2: "full"},
    "operating_status": {1: "off", 2: "humidifying", 3: "drying", 4: "cleaning"},
}


class AirSensor(AirEntity, SensorEntity):
    def __init__(self, entry, key):
        name, unit, device_class = SENSORS[key]
        super().__init__(entry, key, name)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        if key in DIAGNOSTIC_SENSORS:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_entity_registry_enabled_default = False
        if key in ENUM_SENSORS:
            self._attr_options = list(ENUM_SENSORS[key].values())
        elif unit is not None:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        value = self.reading(self.key)
        if self.key in ENUM_SENSORS:
            return ENUM_SENSORS[self.key].get(value)
        # HA states have a 255-character limit; preserve the full opaque value in attributes.
        return value[:255] if isinstance(value, str) else value

    @property
    def extra_state_attributes(self):
        value = self.reading(self.key)
        if isinstance(value, str) and len(value) > 255:
            return {"raw_value": value}
        return None


class AirSwitch(AirEntity, SwitchEntity):
    @property
    def is_on(self):
        return self.reading(self.key)

    async def async_turn_on(self, **kwargs):
        await self.write(self.key, True)

    async def async_turn_off(self, **kwargs):
        await self.write(self.key, False)


class AirSelect(AirEntity, SelectEntity):
    def __init__(self, entry, key, name, choices, *, advanced=False):
        super().__init__(entry, key, name)
        self.choices = choices
        self._attr_options = list(choices.values())
        self._attr_entity_category = EntityCategory.CONFIG
        if advanced:
            self._attr_entity_registry_enabled_default = False

    @property
    def current_option(self):
        return self.choices.get(self.reading(self.key))

    async def async_select_option(self, option):
        for value, label in self.choices.items():
            if option == label:
                await self.write(self.key, value)
                return
        raise HomeAssistantError("Unsupported option")


class FavoriteLevel(AirSelect):
    def __init__(self, entry, key="favorite_level", name="Favorite level"):
        # Measured MC6 target RPMs on firmware 1.0.5; commands remain level IDs.
        rpms = (400, 480, 650, 700, 800, 930, 1100, 1250, 1370, 1530)
        super().__init__(
            entry,
            key,
            name,
            {level: f"Level {level} — {rpm} RPM" for level, rpm in enumerate(rpms)},
        )
        self._attr_entity_category = None


class AdvancedNumber(AirEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_native_step = 1

    def __init__(self, entry, key, name):
        super().__init__(entry, key, name)
        self._attr_native_min_value, self._attr_native_max_value = RANGES[MC6][key]

    @property
    def available(self):
        if self.key in WRITE_ONLY[MC6]:
            return self.coordinator.last_update_success
        return super().available

    @property
    def native_value(self):
        # Debug counters are write-only: never invent a readback value.
        return self.reading(self.key)

    async def async_set_native_value(self, value):
        await self.write(self.key, value)


class AirButton(AirEntity, ButtonEntity):
    def __init__(self, entry, action_key, name):
        super().__init__(entry, action_key, name)
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_entity_registry_enabled_default = False

    @property
    def available(self):
        return self.coordinator.last_update_success

    async def async_press(self):
        try:
            await self.hass.async_add_executor_job(
                self._device.perform_action, self.key
            )
        except (DeviceException, ValueError) as err:
            raise HomeAssistantError(f"Unable to run {self.key}: {err}") from err
        await self.coordinator.async_request_refresh()


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
        entities = [
            AdvancedNumber(entry, key, name)
            for key, name in {
                "update_heartbeat": "AQI update heartbeat (raw)",
                "filter_debug_used_time": "Filter debug used time",
                "filter_debug_used_life": "Filter debug used life",
            }.items()
        ]
    elif platform == "select" and model == MC6:
        entities = [
            FavoriteLevel(entry),
            AirSelect(
                entry, "brightness", "Screen brightness", {0: "Dim", 1: "On", 2: "Mid"}
            ),
            AirSelect(
                entry,
                "fan_level",
                "Fan level",
                {0: "Level 1", 1: "Level 2", 2: "Level 3"},
            ),
            AirSelect(
                entry, "country_code", "Country code", COUNTRY_CODES, advanced=True
            ),
        ]
    elif platform == "button" and model == MC6:
        entities = [
            AirButton(entry, key, name)
            for key, name in {
                "toggle": "Toggle power",
                "reset_filter": "Reset filter life",
                "toggle_mode": "Cycle mode",
                "toggle_fan_level": "Cycle fan level",
            }.items()
        ]
    async_add_entities(entities)
    return True
