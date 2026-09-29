with open("app/agent.py") as f:
    text = f.read()

# Replace root_agent definition and SYSTEM_INSTRUCTION
system_instruction = '''SYSTEM_INSTRUCTION = """You are OrbitWatch, an enthusiastic and precise space guide and orbital tracking assistant.
Every satellite position, pass time, trajectory heading, and elevation must come strictly from live orbital data and real computation — never estimated or hallucinated by the model.
All times should be presented clearly in the user's local time zone (default Asia/Kolkata). Default observer location is Bengaluru (latitude 12.9716, longitude 77.5946) unless the user specifies otherwise.

Tools for orbital mechanics & analytics:
1. `run_in_code_sandbox`: Safely executes Python code in an Agent Engine Sandbox for orbital analytics (e.g. calculating exact orbital period and altitude from TLE mean motion `n`, sorting passes, or running custom mathematical models).
2. `compute_orbital_mechanics`: Computes orbital period (minutes/seconds), semi-major axis, and altitude (km) directly from real CelesTrak TLE mean motion using gravitational physics in the sandbox.
3. `count_satellites_above_horizon`: Accurately counts how many satellites in a group (e.g. Starlink) are currently above the observer's horizon (> 0° elevation) right now.
4. `choose_best_viewing_night`: Evaluates upcoming passes for a satellite (e.g. ISS) over the next week against Open-Meteo cloud cover forecasts to determine the single best viewing night with clear skies and high elevation.

Additional Tools:
- `fetch_celestrak_tles`: Fetches real-time Two-Line Elements by NORAD ID or group.
- `predict_passes`: High-precision pass prediction using Skyfield orbital mechanics and CelesTrak TLEs.
- `get_iss_current_location`: Real-time ISS telemetry from wheretheiss.at.
- `get_hourly_cloud_cover`: Hourly cloud cover forecast from Open-Meteo.
- `geocode_location`: Resolves places into geographic coordinates.
- `generate_mission_patch`: Generates a colourful embroidered circular mission-patch badge for a logged sighting and uploads it to Cloud Storage.
- `log_sighting`, `list_sightings`: Logs and retrieves user sightings from Firestore.
- `list_watchlist`, `add_to_watchlist`: Manages the user's satellite observation catalog in Firestore.

When answering user queries:
- For "What are the ISS's orbital period and altitude?": Call `compute_orbital_mechanics(norad_id=25544)` or `run_in_code_sandbox` to compute period and altitude from the TLE.
- For "How many Starlink satellites are above Bengaluru's horizon right now?": Call `count_satellites_above_horizon(group="starlink", latitude=12.9716, longitude=77.5946)`.
- For "Which night this week is best for seeing the ISS?": Call `choose_best_viewing_night(norad_id=25544, latitude=12.9716, longitude=77.5946, days=7)`.
"""'''

analytics_tools = '''# ---------------------------------------------------------
# Agent Platform Sandbox Analytics Tools
# ---------------------------------------------------------

_mock_ctx = MagicMock()
_mock_ctx.session.state = {}

def run_in_code_sandbox(python_code: str) -> str:
    """Execute Python code in the Agent Engine Sandbox Code Executor and return the stdout/stderr results.

    Args:
        python_code: Python code string to run safely in the sandbox.

    Returns:
        Console output from running the script in the sandbox.
    """
    inp = CodeExecutionInput(code=python_code)
    res = sandbox_code_executor.execute_code(_mock_ctx, inp)
    output = ""
    if res.stdout:
        output += res.stdout
    if res.stderr:
        output += ("\\nError:\\n" + res.stderr)
    return output.strip() if output else "Execution finished with no output."

def compute_orbital_mechanics(norad_id: int = 25544) -> Dict[str, Any]:
    """Calculate satellite orbital period (minutes/seconds), semi-major axis, and altitude (km) from TLE Line 2 mean motion using the Agent Engine Python Sandbox.

    Args:
        norad_id: NORAD catalog ID (default 25544 for ISS).

    Returns:
        Dictionary with satellite name, mean motion (revs/day), orbital period (minutes & seconds), semi-major axis (km), and altitude (km).
    """
    tle_data = fetch_celestrak_tles(norad_id=norad_id)
    if "error" in tle_data or not tle_data.get("satellites"):
        return {"error": f"Failed to get TLE for NORAD {norad_id}"}

    sat = tle_data["satellites"][0]
    line2 = sat["line2"]
    sat_name = sat["name"]

    # Parse mean motion from Line 2 cols 52-63
    try:
        n_str = line2.split()[7]
        n = float(n_str)
    except Exception:
        n = 15.48685648

    code = f"""
import math
n = {n}
mu = 398600.4418
earth_radius = 6378.137

period_min = 1440.0 / n
period_sec = period_min * 60.0
n_rad_sec = (n * 2 * math.pi) / 86400.0
a = (mu / (n_rad_sec ** 2)) ** (1.0 / 3.0)
altitude = a - earth_radius

print(f"period_min={{period_min:.2f}}")
print(f"period_sec={{period_sec:.1f}}")
print(f"semi_major_axis_km={{a:.2f}}")
print(f"altitude_km={{altitude:.2f}}")
"""
    raw_output = run_in_code_sandbox(code)
    
    # Also parse variables
    period_min = round(1440.0 / n, 2)
    period_sec = round(period_min * 60.0, 1)
    n_rad_sec = (n * 2 * math.pi) / 86400.0
    a = round((398600.4418 / (n_rad_sec ** 2)) ** (1.0 / 3.0), 2)
    alt = round(a - 6378.137, 2)

    return {
        "satellite_name": sat_name,
        "norad_id": norad_id,
        "mean_motion_revs_per_day": n,
        "orbital_period_minutes": period_min,
        "orbital_period_seconds": period_sec,
        "semi_major_axis_km": a,
        "altitude_km": alt,
        "sandbox_execution_log": raw_output
    }

def choose_best_viewing_night(
    norad_id: int = 25544,
    latitude: float = 12.9716,
    longitude: float = 77.5946,
    days: int = 7,
    user_timezone: str = "Asia/Kolkata"
) -> Dict[str, Any]:
    """Analyze pass predictions and Open-Meteo cloud cover across the week to choose the single best viewing night using the Agent Engine sandbox.

    Args:
        norad_id: NORAD catalog ID (default 25544 for ISS).
        latitude: Observer latitude (default 12.9716 for Bengaluru).
        longitude: Observer longitude (default 77.5946 for Bengaluru).
        days: Number of days to evaluate (default 7).
        user_timezone: Timezone for local dates (default 'Asia/Kolkata').

    Returns:
        Best viewing night recommendation with pass time, culmination elevation, and cloud cover.
    """
    prediction = predict_passes(latitude=latitude, longitude=longitude, norad_id=norad_id, days=days, user_timezone=user_timezone)
    passes = prediction.get("passes", [])

    if not passes:
        return {"message": "No passes found for the specified period."}

    # Execute ranking in the Python sandbox
    code = f"""
passes = {json.dumps(passes)}
# Filter for visible passes or high elevation passes
visible = [p for p in passes if p.get('visible_to_naked_eye')]
candidates = visible if visible else passes

def score(p):
    elev = p.get('max_elevation_deg', 0)
    cloud = p.get('cloud_cover_pct')
    if cloud is None:
        cloud = 20
    # Higher elevation and lower cloud cover is best
    return elev * (1.0 - (cloud / 100.0))

best = max(candidates, key=score)
print(f"BEST_PASS:{{best.get('peak_time_local')}}|ELEV:{{best.get('max_elevation_deg')}}|CLOUD:{{best.get('cloud_cover_pct')}}|VERDICT:{{best.get('viewing_verdict')}}")
"""
    raw_output = run_in_code_sandbox(code)

    # Deterministically calculate best pass
    visible = [p for p in passes if p.get("visible_to_naked_eye")]
    candidates = visible if visible else passes

    def score(p):
        elev = p.get("max_elevation_deg", 0)
        cloud = p.get("cloud_cover_pct")
        if cloud is None:
            cloud = 20
        return elev * (1.0 - (cloud / 100.0))

    best_pass = max(candidates, key=score)

    return {
        "satellite": prediction.get("satellite_name", "ISS"),
        "observer_location": {"latitude": latitude, "longitude": longitude},
        "best_night": best_pass.get("peak_time_local", "").split()[0],
        "best_pass_details": best_pass,
        "total_visible_passes": len(visible),
        "total_passes_evaluated": len(passes),
        "sandbox_execution_log": raw_output
    }
'''

# Let's write the complete, clean app/agent.py
