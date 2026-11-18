# Changelog

## 0.1.0b1

First beta. After installing, restart Home Assistant, add **Cloudless Biome** under Settings → Devices & services and open the **Biome** page in the sidebar. A new biome starts in a dry run and switches nothing until you turn the dry run off.

### Added

- **A biome day with time windows.** Each device runs in one or more time windows per profile, each end counted from the day's start, its end or a clock time, or around the clock. Drag the bars on the timeline, or the biome day itself and everything that follows it moves along.
- **Intervals,** for example every 15 minutes for 60 seconds between 08:00 and 20:00.
- **Profiles for seasons** that start on a date, when summer time begins or ends, or at the astronomical start of a season, some days before or after if you like, with a soft change of the day's times over several days.
- **A natural day** that follows the sun where you live or at another place, between a shortest and a longest day and centred on the sun's highest point or a time you choose.
- **Reliable switching:** on the minute at every switching point, a check every 10 minutes and after every restart, and a problem sensor when a device does not follow. Switching off that does not take is tried again within seconds.
- **Longest time on,** per kind and per device, 30 seconds for rain (misters included) by default. Biome switches a device off that stays on longer, even after a manual switch or while paused.
- **Switching by hand** from the device or from the page: until the next switching point, for a fixed time, or back to the plan at once.
- **Dimming** for lights: a brightness per profile and, if you like, slow dimming up and down.
- **Dry run and pause.**
- **Measurements and energy:** sensors with their last 24 hours, the power and energy of the devices behind the outlets, and costs with a price per kWh.
- **Notes** and a **log**, in which interval switches are folded away until you ask for them.
- Devices are added from a search with rooms and kinds; the biome's own room comes first. Profiles and devices can also be set up in Home Assistant's dialogs.
