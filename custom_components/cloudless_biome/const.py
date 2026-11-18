"""Constants for Cloudless Biome."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "cloudless_biome"
NAME: Final = "Cloudless Biome"

PANEL_URL: Final = "cloudless-biome"
URL_STATIC: Final = "/cloudless_biome_static"

STORAGE_VERSION: Final = 1
LOG_SIZE: Final = 1000
# Switches of interval windows go to a log of their own, so they do not push everything else out.
PULSE_LOG_SIZE: Final = 500
SAVE_DELAY: Final = 5

# Besides the switching points, Biome checks all devices this often.
CHECK_INTERVAL_MINUTES: Final = 10

# A command counts as failed when the device still differs after this many checks.
MAX_ATTEMPTS: Final = 3

SUBENTRY_PROFILE: Final = "profile"
SUBENTRY_DEVICE: Final = "device"

CONF_PROFILE_NAME: Final = "profile_name"
CONF_DAY_START: Final = "day_start"
CONF_DAY_END: Final = "day_end"
CONF_START_DATE: Final = "start_date"
CONF_COPY_FROM: Final = "copy_from"
CONF_TRANSITION: Final = "transition"

CONF_ENTITY_ID: Final = "entity_id"
CONF_KIND: Final = "kind"
CONF_MANUAL: Final = "manual"
CONF_MANUAL_MINUTES: Final = "manual_minutes"
CONF_PROFILES: Final = "profiles"
CONF_ACTIVE: Final = "active"
CONF_ON_OFFSET: Final = "on_offset"
CONF_OFF_OFFSET: Final = "off_offset"
CONF_BRIGHTNESS: Final = "brightness"
CONF_RAMP: Final = "ramp"
CONF_MODE: Final = "mode"
CONF_ON_TIME: Final = "on_time"
CONF_OFF_TIME: Final = "off_time"
CONF_ORDER: Final = "order"
CONF_SPANS: Final = "spans"
CONF_MAX_ON: Final = "max_on"
CONF_START_EVENT: Final = "start_event"
CONF_START_OFFSET: Final = "start_offset"
CONF_DAY_MODE: Final = "day_mode"

# Biome-wide settings, in the config entry's options.
OPT_MAX_ON: Final = "max_on"  # seconds per kind; 0 or missing means no limit
OPT_NATURAL: Final = "natural"
OPT_SENSORS: Final = "sensors"
OPT_PRICE: Final = "price"
DEFAULT_MAX_ON: Final = {"rain": 30}

DAY_FIXED: Final = "fixed"
DAY_NATURAL: Final = "natural"
DAY_MODES: Final = (DAY_FIXED, DAY_NATURAL)

REFS: Final = ("start", "end", "clock")

# How a device runs in a profile: in time windows, or around the clock.
MODE_WINDOWS: Final = "windows"
MODE_ALWAYS: Final = "always"
MODES: Final = (MODE_WINDOWS, MODE_ALWAYS)
# Before time windows there was one window, with the biome day or at fixed times.
LEGACY_DAY: Final = "day"
LEGACY_FIXED: Final = "fixed"

NOTES_LIMIT: Final = 100_000

KINDS: Final = ("light", "heat", "rain", "air", "other")
KIND_ICONS: Final = {
    "light": "mdi:lightbulb-outline",
    "heat": "mdi:heat-wave",
    "rain": "mdi:weather-pouring",
    "air": "mdi:fan",
    "other": "mdi:power-socket-eu",
}

# What happens when someone switches a device by hand.
MANUAL_NEXT: Final = "next"  # keep it until the device's next switching point
MANUAL_DURATION: Final = "duration"  # keep it for a fixed time
MANUAL_NEVER: Final = "never"  # restore the plan at once
MANUAL_MODES: Final = (MANUAL_NEXT, MANUAL_DURATION, MANUAL_NEVER)

OFFSET_LIMIT: Final = 720
RAMP_LIMIT: Final = 240
TRANSITION_LIMIT: Final = 60
