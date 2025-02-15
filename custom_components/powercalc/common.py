from __future__ import annotations

import re
from typing import NamedTuple

import homeassistant.helpers.device_registry as dr
import homeassistant.helpers.entity_registry as er
import voluptuous as vol
from homeassistant.components.light import ATTR_SUPPORTED_COLOR_MODES
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers.template import is_number

from .const import (
    CONF_CREATE_ENERGY_SENSOR,
    CONF_CREATE_ENERGY_SENSORS,
    CONF_CREATE_GROUP,
    CONF_DAILY_FIXED_ENERGY,
    CONF_POWER_SENSOR_ID,
    DUMMY_ENTITY_ID,
)
from .errors import SensorConfigurationError


class SourceEntity(NamedTuple):
    object_id: str
    entity_id: str
    domain: str
    unique_id: str | None = None
    name: str | None = None
    supported_color_modes: list[str] | None = None
    entity_entry: er.RegistryEntry | None = None
    device_entry: dr.DeviceEntry | None = None


async def create_source_entity(entity_id: str, hass: HomeAssistant) -> SourceEntity:
    """Create object containing all information about the source entity"""

    if entity_id == DUMMY_ENTITY_ID:
        return SourceEntity(
            object_id=DUMMY_ENTITY_ID, entity_id=DUMMY_ENTITY_ID, domain=DUMMY_ENTITY_ID
        )

    source_entity_domain, source_object_id = split_entity_id(entity_id)

    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get(entity_id)

    dev = dr.async_get(hass)
    if entity_entry and entity_entry.device_id:
        device_entry = dev.async_get(entity_entry.device_id)
    else:
        device_entry = None

    unique_id = None
    supported_color_modes = []
    if entity_entry:
        source_entity_name = entity_entry.name or entity_entry.original_name
        source_entity_domain = entity_entry.domain
        unique_id = entity_entry.unique_id
        if entity_entry.capabilities:
            supported_color_modes = entity_entry.capabilities.get(
                ATTR_SUPPORTED_COLOR_MODES
            )
    else:
        source_entity_name = source_object_id.replace("_", " ")

    entity_state = hass.states.get(entity_id)
    if entity_state:
        source_entity_name = entity_state.name
        supported_color_modes = entity_state.attributes.get(ATTR_SUPPORTED_COLOR_MODES)

    return SourceEntity(
        source_object_id,
        entity_id,
        source_entity_domain,
        unique_id,
        source_entity_name,
        supported_color_modes or [],
        entity_entry,
        device_entry,
    )


def get_merged_sensor_configuration(*configs: dict, validate: bool = True) -> dict:
    """Merges configuration from multiple levels (global, group, sensor) into a single dict"""

    exclude_from_merging = [
        CONF_NAME,
        CONF_ENTITY_ID,
        CONF_UNIQUE_ID,
        CONF_POWER_SENSOR_ID,
    ]
    num_configs = len(configs)

    merged_config = {}
    for i, config in enumerate(configs, 1):
        config_copy = config.copy()
        # Remove config properties which are only allowed on the deepest level
        if i < num_configs:
            for key in exclude_from_merging:
                if key in config:
                    config_copy.pop(key)

        merged_config.update(config_copy)

    if CONF_CREATE_ENERGY_SENSOR not in merged_config:
        merged_config[CONF_CREATE_ENERGY_SENSOR] = merged_config.get(
            CONF_CREATE_ENERGY_SENSORS
        )

    if CONF_DAILY_FIXED_ENERGY in merged_config and CONF_ENTITY_ID not in merged_config:
        merged_config[CONF_ENTITY_ID] = DUMMY_ENTITY_ID

    if (
        validate
        and CONF_CREATE_GROUP not in merged_config
        and CONF_ENTITY_ID not in merged_config
    ):
        raise SensorConfigurationError(
            "You must supply an entity_id in the configuration, see the README"
        )

    return merged_config


def validate_name_pattern(value: str) -> str:
    """Validate that the naming pattern contains {}."""
    regex = re.compile(r"{}")
    if not regex.search(value):
        raise vol.Invalid("Naming pattern must contain {}")
    return value


def validate_is_number(value: str) -> str:
    """Validate value is a number."""
    if is_number(value):
        return value
    raise vol.Invalid("Value is not a number")
