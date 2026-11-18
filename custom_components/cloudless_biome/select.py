"""Choose the profile (season) of a biome."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import BiomeConfigEntry
from .biome import Biome
from .entity import BiomeEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: BiomeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up the profile select."""
    async_add_entities([ProfileSelect(entry.runtime_data)])


class ProfileSelect(BiomeEntity, SelectEntity):
    """The active profile. With dated profiles, a choice lasts until the next season starts."""

    _attr_icon = "mdi:calendar-sync-outline"

    def __init__(self, biome: Biome) -> None:
        """Initialize."""
        super().__init__(biome, "profile")

    def _labels(self) -> dict[str, str]:
        """Return a unique label per profile id."""
        out: dict[str, str] = {}
        for profile in self.biome.profiles:
            label, n = profile.name, 2
            while label in out.values():
                label = f"{profile.name} ({n})"
                n += 1
            out[profile.id] = label
        return out

    @property
    def options(self) -> list[str]:
        """Return the profiles."""
        return list(self._labels().values())

    @property
    def current_option(self) -> str | None:
        """Return the profile that applies today."""
        profile = self.biome.plan.profile(dt_util.now().date())
        return self._labels().get(profile.id) if profile else None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Whether the profile was chosen by hand, and until when."""
        plan = self.biome.plan
        manual = plan.manual_applies(dt_util.now().date())
        return {
            "manual": manual,
            "until": (self.biome.manual or {}).get("until") if manual else None,
            "automatic": plan.automatic,
        }

    async def async_select_option(self, option: str) -> None:
        """Choose a profile by hand."""
        profile_id = next((k for k, v in self._labels().items() if v == option), None)
        await self.biome.async_set_profile(profile_id)
