"""Serve the Biome page in the sidebar."""

from __future__ import annotations

import hashlib
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import PANEL_URL, URL_STATIC

FILES = Path(__file__).parent / "frontend"
PANEL_FILE = "biome-panel.js"


def _versions() -> dict[str, str]:
    """Return a short hash per file, so browsers pick up a new version at once."""
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()[:10] for path in FILES.glob("*.js")}


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Register the static files and the sidebar page."""
    await hass.http.async_register_static_paths([StaticPathConfig(URL_STATIC, str(FILES), cache_headers=True)])
    versions = await hass.async_add_executor_job(_versions)
    # One version for all modules: the page loads the others with the same query.
    combined = hashlib.sha256("".join(v for _, v in sorted(versions.items())).encode()).hexdigest()[:12]
    panel_url = f"{URL_STATIC}/{PANEL_FILE}?v={combined}"
    if PANEL_URL in hass.data.get(frontend.DATA_PANELS, {}):
        return
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL,
        webcomponent_name="biome-panel",
        sidebar_title="Biome",
        sidebar_icon="mdi:leaf",
        module_url=panel_url,
        require_admin=False,
    )
