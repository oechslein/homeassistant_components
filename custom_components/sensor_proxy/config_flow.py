import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID

from .const import DOMAIN


class SensorProxyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a config flow for Sensor Proxy."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        if user_input is not None:
            unique_id = user_input.get(CONF_UNIQUE_ID)
            if unique_id:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required("source_entity_id"): str,
                vol.Required(CONF_UNIQUE_ID): str,
                vol.Required(CONF_NAME): str,
                vol.Optional("device_id"): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema)
