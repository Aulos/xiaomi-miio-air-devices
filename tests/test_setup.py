"""Check the real integration coordinator selection and manual config flow."""

from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.xiaomi_miio import async_create_miio_device_and_coordinator
from custom_components.xiaomi_miio.air_devices import CA6, MC6, AirDevice
from custom_components.xiaomi_miio.config_flow import XiaomiMiioFlowHandler
from custom_components.xiaomi_miio.const import CONF_FLOW_TYPE


@pytest.mark.asyncio
@pytest.mark.parametrize("model", [MC6, CA6])
async def test_coordinator_uses_new_driver_and_reads_first_state(tmp_path, model):
    hass = HomeAssistant(str(tmp_path))
    entry = ConfigEntry(
        domain="xiaomi_miio",
        title="Test",
        version=1,
        minor_version=1,
        data={
            "model": model,
            "host": "192.0.2.1",
            "token": "0" * 32,
            "mac": None,
            CONF_FLOW_TYPE: "device",
        },
        options={},
        source="user",
        unique_id="test",
        state=ConfigEntryState.SETUP_IN_PROGRESS,
        discovery_keys=MappingProxyType({}),
        subentries_data=[],
    )
    try:
        with patch.object(
            AirDevice, "status", return_value={"power": True, "mode": 0}
        ) as status:
            await async_create_miio_device_and_coordinator(hass, entry)
        assert type(entry.runtime_data.device) is AirDevice
        assert entry.runtime_data.device.air_model == model
        assert entry.runtime_data.device_coordinator.data["power"] is True
        status.assert_called_once()
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("model", [MC6, CA6])
async def test_manual_setup_accepts_model_without_cloud(tmp_path, model):
    hass = HomeAssistant(str(tmp_path))
    flow = XiaomiMiioFlowHandler()
    flow.hass = hass
    flow.context = {"source": "user"}
    flow.async_set_unique_id = AsyncMock(return_value=None)
    connector = Mock()
    connector.async_connect_device = AsyncMock()
    connector.device_info = SimpleNamespace(
        model=model, mac_address="00:00:00:00:00:01"
    )
    try:
        with patch(
            "custom_components.xiaomi_miio.config_flow.ConnectXiaomiDevice",
            return_value=connector,
        ):
            result = await flow.async_step_manual(
                {"host": "192.0.2.1", "token": "0" * 32}
            )
        assert result["type"] == "create_entry"
        assert result["data"]["model"] == model
        assert result["data"][CONF_FLOW_TYPE] == "device"
    finally:
        await hass.async_stop()
