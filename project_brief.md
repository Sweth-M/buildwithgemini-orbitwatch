# My agent: OrbitWatch
One-liner: A conversational agent that helps skywatchers, amateur astronomers, and curious people spot real satellites (ISS, Hubble, Tiangong, Starlink) passing over their location with live orbital mechanics, weather-aware visibility predictions, and digital mission-patch badges.

Behavior:
An enthusiastic but precise space guide. Every position, pass time, and elevation must come from live orbital data and real computation — never estimated by the model. All times are displayed in the user's local time zone (default Asia/Kolkata).

Data (Firestore collections):
- "orbit_satellites" (watchlist): name, norad_id, category (station, telescope, weather, earth_observation, constellation), description, patch_url. Seeded with 5: ISS (25544), Tiangong/Tianhe (48274), Hubble Space Telescope (20580), NOAA 19 (33591), Terra (25994).
- "orbit_sightings": sighting_id, satellite_name, norad_id, observed_at, location_name, max_elevation_deg, notes, patch_url, created_at.

Tools:
- list_watchlist
- add_to_watchlist
- log_sighting
- list_sightings

External APIs (free, no auth key required):
- CelesTrak GP API for current orbital elements (TLEs): `https://celestrak.org/NORAD/elements/gp.php?CATNR=<norad_id>&FORMAT=tle` and group queries (`GROUP=stations`, `GROUP=starlink`).
- wheretheiss.at (`https://api.wheretheiss.at/v1/satellites/25544`) for the ISS live latitude, longitude, altitude, and velocity.
- Open-Meteo (`https://api.open-meteo.com/v1/forecast?hourly=cloud_cover`) for cloud cover percentage at pass times.

Tool coverage:
- Memory: Remembers the user's location (city and geographic coordinates), observing hours/schedule availability, favorite satellites, and optical equipment (naked eye, binoculars, or telescope).
- Tools: list_watchlist, add_to_watchlist, log_sighting, list_sightings, CelesTrak TLE lookups, WhereTheISS telemetry fetch, Open-Meteo sky transparency check.
- Catalog/UI (A2UI): Upcoming passes table (satellite, date, start time, max elevation, direction, visible yes/no, cloud cover %); Satellite detail card (name, NORAD ID, category, altitude, orbital period, next visible pass, patch image); Sightings log table.
- Image gen: Generates a colorful embroidered mission-patch style badge for a logged sighting (satellite silhouette, observation date, location name in the border), uploaded to Cloud Storage with public URL persisted on the sighting record.
- Sandbox:
  - Primary: Pass prediction using `skyfield` with CelesTrak TLEs to compute passes for the next N days (rise/culmination/set times, max elevation, compass direction, and sunlit-in-darkness visibility calculation). If `skyfield` is not available in the sandbox, computes passes via function tool and uses the sandbox for orbital analytics.
  - Analytics: Calculate orbital period and altitude from TLE mean motion; count how many satellites in a constellation group (e.g., Starlink) are above the user's horizon right now; summarize best viewing night of the week combining pass elevation and cloud cover; chart pass elevations.

Recommended for every project: memory, storage, tools, image generation, A2UI
Agent-specific / stretch (pick what fits):
- Code sandbox for orbital mechanics and pass elevation calculations
- Live external APIs (CelesTrak, WhereTheISS, Open-Meteo)
- Omni video of a pass across the night sky
- Eval set checking every time and elevation the agent states matches tool output
- Real-time Starlink train overhead alerts
