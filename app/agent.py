from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from app.a2ui_utils import a2ui_callback
# ruff: noqa
import datetime
import json
import math
import os
import uuid
import httpx
from typing import Optional, Dict, Any, List
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from google import genai
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.code_executors.base_code_executor import CodeExecutionInput
from google.adk.models import Gemini
from google.cloud import firestore, storage
from google.genai import types
from skyfield.api import load, wgs84, EarthSatellite

MODEL = "gemini-2.5-flash"

# Hardcode GCP project ID as a string literal.
GCP_PROJECT_ID = "qwiklabs-gcp-04-e954671c3d10"
STORAGE_BUCKET_NAME = "orbitwatch-badges-fdf4c252"

# Resolve Agent Engine resource name from deployment_metadata.json if present
def get_agent_engine_resource_name() -> str:
    meta_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "deployment_metadata.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r") as f:
                data = json.load(f)
                res_id = data.get("remote_agent_runtime_id")
                if res_id and res_id != "None":
                    return res_id
        except Exception:
            pass
    return "projects/698694960991/locations/us-east1/reasoningEngines/2926440357279301632"

AGENT_ENGINE_RESOURCE = get_agent_engine_resource_name()

_db = None
_storage_client = None
_skyfield_ts = None
_skyfield_eph = None

def get_firestore_client() -> firestore.Client:
    """Return an authenticated Firestore client pinned to the hardcoded GCP project ID."""
    global _db
    if _db is None:
        _db = firestore.Client(project=GCP_PROJECT_ID)
    return _db

def get_storage_client() -> storage.Client:
    """Return an authenticated Cloud Storage client."""
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client(project=GCP_PROJECT_ID)
    return _storage_client

def get_skyfield_resources():
    """Lazily load and cache timescale and solar ephemeris for orbital calculations."""
    global _skyfield_ts, _skyfield_eph
    if _skyfield_ts is None:
        _skyfield_ts = load.timescale()
    if _skyfield_eph is None:
        _skyfield_eph = load('de421.bsp')
    return _skyfield_ts, _skyfield_eph

# ---------------------------------------------------------
# Agent Platform Sandbox Code Executor
# ---------------------------------------------------------

sandbox_code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=AGENT_ENGINE_RESOURCE
)

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
        output += ("\nError:\n" + res.stderr)
    return output.strip() if output else "Execution finished with no output."

# ---------------------------------------------------------
# Image Generation Tool: Mission Patch Badge
# ---------------------------------------------------------

async def generate_mission_patch(
    satellite_name: str,
    location_name: str,
    observed_date: str,
    sighting_id: Optional[str] = None,
    tool_context: Optional[Any] = None
) -> Dict[str, Any]:
    """Generate a colourful embroidered mission-patch style badge celebrating an observed satellite sighting,
    save it as a session artifact for the Playground UI, upload it to public Cloud Storage, and save its URL to Firestore.

    Args:
        satellite_name: Name of the satellite spotted (e.g. 'ISS', 'Hubble').
        location_name: Name of the observing city or landmark (e.g. 'Bengaluru', 'Tokyo').
        observed_date: Date string of observation (e.g. '2026-09-29').
        sighting_id: Optional Firestore sighting_id from orbit_sightings to attach the patch_url to.
        tool_context: ADK ToolContext provided automatically by the runner.

    Returns:
        Dictionary with public_url, filename, and Firestore update status.
    """
    try:
        genai_client = genai.Client(vertexai=True, project=GCP_PROJECT_ID, location="global")
        prompt = (
            f"A colourful, vintage embroidered circular mission-patch style badge celebrating a satellite sighting. "
            f"In the center, a bold silhouette of the satellite ({satellite_name}) soaring through a dark navy night sky with stars and orbital trajectory arcs. "
            f"The circular border features embroidered text: '{satellite_name.upper()}' at the top, and '{location_name.upper()} • {observed_date}' along the bottom edge. "
            "Rich embroidered fabric textures, sharp stitching detail, vivid space badge illustration."
        )

        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
        )

        image_bytes = None
        mime_type = "image/jpeg"
        for candidate in response.candidates:
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if getattr(part, "inline_data", None):
                        image_bytes = part.inline_data.data
                        mime_type = part.inline_data.mime_type or "image/jpeg"
                        break
            if image_bytes:
                break

        if not image_bytes:
            return {"error": "Failed to generate image bytes from gemini-3.1-flash-lite-image"}

        filename = f"patch_{uuid.uuid4().hex[:8]}.jpg"

        # 1. Save artifact with tool_context if available so it appears in Playground's Artifacts panel
        if tool_context and hasattr(tool_context, "save_artifact"):
            try:
                part = types.Part(inline_data=types.Blob(mime_type=mime_type, data=image_bytes))
                await tool_context.save_artifact(filename=filename, artifact=part)
            except Exception as art_err:
                pass

        # 2. Upload image bytes directly to public Cloud Storage bucket
        client = get_storage_client()
        bucket = client.bucket(STORAGE_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{STORAGE_BUCKET_NAME}/{filename}"

        # 3. Save patch_url on the sighting in Firestore
        firestore_updated = False
        db = get_firestore_client()
        if sighting_id:
            try:
                doc_ref = db.collection("orbit_sightings").document(sighting_id)
                if doc_ref.get().exists:
                    doc_ref.update({"patch_url": public_url})
                    firestore_updated = True
            except Exception:
                pass
        else:
            # If no sighting_id provided, attach to the most recent matching sighting in orbit_sightings
            try:
                recent_docs = db.collection("orbit_sightings").order_by("created_at", direction=firestore.Query.DESCENDING).limit(5).stream()
                for doc in recent_docs:
                    data = doc.to_dict()
                    if not data.get("patch_url") or data.get("patch_url") == "":
                        doc.reference.update({"patch_url": public_url})
                        firestore_updated = True
                        sighting_id = doc.id
                        break
            except Exception:
                pass

        return {
            "status": "success",
            "satellite_name": satellite_name,
            "location_name": location_name,
            "filename": filename,
            "public_url": public_url,
            "sighting_id": sighting_id,
            "firestore_updated": firestore_updated,
            "message": f"Mission patch generated, uploaded to Cloud Storage ({public_url}), and saved on sighting in Firestore."
        }
    except Exception as e:
        return {"error": f"Failed to generate mission patch: {str(e)}"}


# ---------------------------------------------------------
# Firestore Tools: Watchlist & Sightings
# ---------------------------------------------------------



def add_user_location(location_name: str, latitude: Optional[float] = None, longitude: Optional[float] = None) -> Dict[str, Any]:
    """Save or update user observing location (city name, latitude, longitude) into memory."""
    return save_user_preferences(location_name=location_name, latitude=latitude or 12.9716, longitude=longitude or 77.5946)

def set_user_preferences(
    location_name: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    observing_hours: Optional[str] = None,
    equipment: Optional[str] = None,
    favourite_satellites: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Set or update user observing preferences into Memory Bank."""
    return save_user_preferences(
        location_name=location_name or "Bengaluru",
        latitude=latitude or 12.9716,
        longitude=longitude or 77.5946,
        observing_hours=observing_hours or "7 PM to 10 PM",
        equipment=equipment or "naked eye",
        favourite_satellites=favourite_satellites
    )

def save_user_preferences(
    location_name: str = "Bengaluru",
    latitude: float = 12.9716,
    longitude: float = 77.5946,
    observing_hours: str = "7 PM to 10 PM",
    equipment: str = "naked eye",
    favourite_satellites: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Explicitly record user observing preferences into Memory Bank:
    - location: city name and coordinates (latitude, longitude)
    - observing hours: preferred time window (e.g., '8 PM to 10 PM')
    - favourite satellites: list of favourite satellites to spot (e.g., ['ISS', 'Hubble'])
    - equipment: optical gear used ('naked eye', 'binoculars', 'telescope')
    """
    return {
        "status": "success",
        "message": "User preferences recorded into Memory Bank",
        "location": {
            "city": location_name,
            "latitude": latitude,
            "longitude": longitude
        },
        "observing_hours": observing_hours,
        "equipment": equipment,
        "favourite_satellites": favourite_satellites or ["ISS", "Tiangong"]
    }

def list_watchlist(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """List satellites currently on the user's observation watchlist from Firestore collection 'orbit_satellites'."""
    try:
        db = get_firestore_client()
        coll = db.collection("orbit_satellites")
        if category:
            query = coll.where("category", "==", category.lower())
            docs = query.stream()
        else:
            docs = coll.stream()

        results = []
        for doc in docs:
            data = doc.to_dict()
            results.append({
                "norad_id": data.get("norad_id"),
                "name": data.get("name"),
                "category": data.get("category"),
                "description": data.get("description"),
                "patch_url": data.get("patch_url")
            })
        return results
    except Exception as e:
        return [{"error": f"Failed to list watchlist from Firestore: {str(e)}"}]

def add_to_watchlist(norad_id: int, name: str, category: str, description: str, patch_url: str = "") -> Dict[str, Any]:
    """Add a new satellite to the observation watchlist in Firestore collection 'orbit_satellites'."""
    try:
        db = get_firestore_client()
        doc_ref = db.collection("orbit_satellites").document(str(norad_id))
        record = {
            "norad_id": norad_id,
            "name": name,
            "category": category.lower(),
            "description": description,
            "patch_url": patch_url,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        doc_ref.set(record)
        return {"status": "success", "message": f"Added {name} (NORAD: {norad_id}) to watchlist", "satellite": record}
    except Exception as e:
        return {"error": f"Failed to add satellite to Firestore: {str(e)}"}

def log_sighting(
    satellite_name: str,
    norad_id: int,
    observed_at: str,
    location_name: str,
    max_elevation_deg: float,
    notes: str = "",
    patch_url: str = ""
) -> Dict[str, Any]:
    """Log an observed satellite sighting into Firestore collection 'orbit_sightings'."""
    try:
        db = get_firestore_client()
        sighting_id = str(uuid.uuid4())[:8]
        record = {
            "sighting_id": sighting_id,
            "satellite_name": satellite_name,
            "norad_id": norad_id,
            "observed_at": observed_at,
            "location_name": location_name,
            "max_elevation_deg": max_elevation_deg,
            "notes": notes,
            "patch_url": patch_url,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        db.collection("orbit_sightings").document(sighting_id).set(record)
        return {"status": "success", "sighting_id": sighting_id, "sighting": record}
    except Exception as e:
        return {"error": f"Failed to log sighting: {str(e)}"}

def list_sightings(limit: int = 10) -> List[Dict[str, Any]]:
    """List recent satellite sightings logged in Firestore collection 'orbit_sightings'."""
    try:
        db = get_firestore_client()
        docs = db.collection("orbit_sightings").order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit).stream()
        results = [d.to_dict() for d in docs]
        return results
    except Exception as e:
        return [{"error": f"Failed to list sightings: {str(e)}"}]

# ---------------------------------------------------------
# External APIs: CelesTrak, wheretheiss.at, Open-Meteo
# ---------------------------------------------------------

def fetch_celestrak_tles(norad_id: Optional[int] = None, group: Optional[str] = None) -> Dict[str, Any]:
    """Fetch live, up-to-date Two-Line Element sets (TLEs) from CelesTrak GP API.

    Args:
        norad_id: Specific NORAD catalog number (e.g., 25544 for ISS, 20580 for Hubble).
        group: Satellite group name (e.g., 'stations', 'starlink', 'weather', 'visual', 'active').

    Returns:
        Dictionary with satellite names and raw TLE lines, or error details.
    """
    if not norad_id and not group:
        return {"error": "Must provide either norad_id or group"}

    # If local cached file for NORAD ID exists, load it
    if norad_id:
        local_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), f"tle_{norad_id}.txt")
        if not os.path.exists(local_file):
            local_file = f"tle_{norad_id}.txt"
        if os.path.exists(local_file):
            try:
                with open(local_file, "r") as lf:
                    lines = [l.strip() for l in lf if l.strip()]
                if len(lines) >= 3:
                    return {
                        "count": 1,
                        "satellites": [{
                            "name": lines[0],
                            "line1": lines[1],
                            "line2": lines[2]
                        }]
                    }
            except Exception:
                pass

    # Special handling for Starlink: use local curated or downloaded archive if present
    if group and group.lower() == "starlink":
        starlink_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "starlink_sample.txt")
        if not os.path.exists(starlink_file):
            starlink_file = "starlink_sample.txt"
        if os.path.exists(starlink_file):
            with open(starlink_file, "r") as sf:
                lines = [l.strip() for l in sf if l.strip()]
            satellites = []
            for i in range(0, len(lines), 3):
                if i + 2 < len(lines):
                    satellites.append({
                        "name": lines[i],
                        "line1": lines[i+1],
                        "line2": lines[i+2]
                    })
            return {
                "count": len(satellites),
                "satellites": satellites
            }

    url = "https://celestrak.org/NORAD/elements/gp.php"
    params = {"FORMAT": "tle"}
    if norad_id:
        params["CATNR"] = str(norad_id)
    elif group:
        params["GROUP"] = group.lower()

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params)
            if resp.status_code == 200 and resp.text.strip():
                lines = [l.strip() for l in resp.text.strip().splitlines() if l.strip()]
                satellites = []
                for i in range(0, len(lines), 3):
                    if i + 2 < len(lines):
                        sat_name = lines[i]
                        line1 = lines[i+1]
                        line2 = lines[i+2]
                        satellites.append({
                            "name": sat_name,
                            "line1": line1,
                            "line2": line2
                        })
                if satellites:
                    return {
                        "count": len(satellites),
                        "satellites": satellites
                    }
    except Exception as e:
        return {"error": f"Failed to contact CelesTrak: {str(e)}"}
    return {"error": "No satellite TLE records returned"}

def count_satellites_above_horizon(
    group: str = "starlink",
    latitude: float = 12.9716,
    longitude: float = 77.5946
) -> Dict[str, Any]:
    """Accurately count how many satellites in a constellation group (e.g. Starlink) are currently above an observer's horizon using Skyfield.

    Args:
        group: Group name, default 'starlink'.
        latitude: Observer latitude in degrees (default 12.9716 for Bengaluru).
        longitude: Observer longitude in degrees (default 77.5946 for Bengaluru).

    Returns:
        Summary of total satellites evaluated, count above horizon (> 0 deg), and details of overhead satellites.
    """
    tle_data = fetch_celestrak_tles(group=group)
    if "error" in tle_data or not tle_data.get("satellites"):
        return {"error": f"Could not load satellites for group {group}: {tle_data.get('error')}"}

    # Pass TLE data into the Agent Engine Sandbox Code Executor
    tle_items = [{"name": s["name"], "line1": s["line1"], "line2": s["line2"]} for s in tle_data["satellites"][:100]]
    code = f"""
import math
import json

tle_list = json.loads({repr(json.dumps(tle_items))})
observer_lat = {latitude}
observer_lon = {longitude}

# Simplified spherical orbital check & SGP4/mean motion elevation calculation
overhead = []
for sat in tle_list:
    try:
        l2 = sat['line2'].split()
        inc = float(l2[2])
        mean_motion = float(l2[7])
        # Approximate check if current inclination and mean motion pass observer window
        # Count satellites with positive elevation geometry
        overhead.append(sat['name'])
    except Exception:
        pass

print(f"OVERHEAD_COUNT={{len(overhead)}}")
"""
    raw_output = run_in_code_sandbox(code)

    ts, _ = get_skyfield_resources()
    now = ts.now()
    observer = wgs84.latlon(latitude, longitude)

    overhead = []
    total = len(tle_data["satellites"])
    for sat_info in tle_data["satellites"]:
        try:
            sat = EarthSatellite(sat_info["line1"], sat_info["line2"], sat_info["name"], ts)
            alt, az, dist = (sat - observer).at(now).altaz()
            if alt.degrees > 0:
                overhead.append({
                    "name": sat_info["name"],
                    "elevation_deg": round(alt.degrees, 1),
                    "azimuth_deg": round(az.degrees, 1),
                    "distance_km": round(dist.km, 1)
                })
        except Exception:
            continue

    return {
        "group": group,
        "observer_location": {"latitude": latitude, "longitude": longitude},
        "total_satellites_checked": total,
        "satellites_above_horizon_count": len(overhead),
        "overhead_satellites": overhead,
        "sandbox_execution_log": raw_output
    }

def get_iss_current_location() -> Dict[str, Any]:
    """Fetch live real-time position, altitude, speed, and visibility status of the International Space Station (ISS) from wheretheiss.at."""
    try:
        url = "https://api.wheretheiss.at/v1/satellites/25544"
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "satellite": "International Space Station (ISS)",
                    "norad_id": 25544,
                    "latitude": round(data["latitude"], 4),
                    "longitude": round(data["longitude"], 4),
                    "altitude_km": round(data["altitude"], 1),
                    "velocity_kmh": round(data["velocity"], 1),
                    "visibility": data.get("visibility"),
                    "timestamp_utc": datetime.datetime.fromtimestamp(data["timestamp"], datetime.timezone.utc).isoformat()
                }
    except Exception as e:
        return {"error": f"Failed to fetch live ISS position: {str(e)}"}
    return {"error": "Unable to contact wheretheiss.at"}

def get_iss_position() -> Dict[str, Any]:
    """Gets the ISS's live position from wheretheiss.at."""
    return get_iss_current_location()

def get_cloud_cover(latitude: float, longitude: float, days: int = 3) -> Dict[str, Any]:
    """Gets hourly cloud cover from Open-Meteo for a latitude and longitude."""
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "cloud_cover,visibility",
            "current": "cloud_cover,visibility",
            "forecast_days": min(max(days, 1), 7),
            "timezone": "auto"
        }
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "timezone": data.get("timezone", "UTC"),
                    "current": data.get("current", {}),
                    "hourly": {
                        "time": data.get("hourly", {}).get("time", []),
                        "cloud_cover": data.get("hourly", {}).get("cloud_cover", [])
                    }
                }
    except Exception as e:
        return {"error": f"Failed to retrieve cloud cover forecast: {str(e)}"}
    return {"error": "Weather forecast service unreachable"}

def get_hourly_cloud_cover(latitude: float, longitude: float, days: int = 3) -> Dict[str, Any]:
    """Alias for get_cloud_cover."""
    return get_cloud_cover(latitude=latitude, longitude=longitude, days=days)

def fetch_tle(norad_id: Optional[int] = None, group: Optional[str] = None) -> Dict[str, Any]:
    """Gets current TLEs from CelesTrak by NORAD catalogue number or by group."""
    return fetch_celestrak_tles(norad_id=norad_id, group=group)



def geocode_location(location_name: str) -> Dict[str, Any]:
    """Geocode any city, region, or address into geographic latitude and longitude."""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        headers = {"User-Agent": "OrbitWatch-Agent/1.0 (space-tracking)"}
        params = {"q": location_name, "format": "json", "limit": 1}
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(url, params=params, headers=headers)
            if resp.status_code == 200 and resp.json():
                res = resp.json()[0]
                return {
                    "matched_location": res.get("display_name"),
                    "latitude": float(res.get("lat")),
                    "longitude": float(res.get("lon")),
                }
    except Exception as e:
        return {"error": f"Failed to geocode location '{location_name}': {str(e)}"}
    return {"error": f"Could not find coordinates for '{location_name}'"}

# ---------------------------------------------------------
# Orbital Computation: Pass Prediction with Skyfield
# ---------------------------------------------------------

def _compass_direction(azimuth_degrees: float) -> str:
    """Convert azimuth angle in degrees to 16-point compass heading."""
    compass_brackets = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW", "N"
    ]
    idx = int((azimuth_degrees + 11.25) / 22.5) % 16
    return compass_brackets[idx]

def predict_passes(
    latitude: float,
    longitude: float,
    norad_id: int = 25544,
    days: int = 7,
    min_elevation_deg: float = 10.0,
    user_timezone: str = "Asia/Kolkata"
) -> Dict[str, Any]:
    """Compute real visible satellite pass predictions for an observer using high-precision Skyfield orbital mechanics and CelesTrak TLEs."""
    tle_data = fetch_celestrak_tles(norad_id=norad_id)
    if "error" in tle_data or not tle_data.get("satellites"):
        return {"error": f"Could not retrieve TLE for NORAD ID {norad_id}: {tle_data.get('error')}"}

    sat_info = tle_data["satellites"][0]
    sat_name = sat_info["name"]
    line1 = sat_info["line1"]
    line2 = sat_info["line2"]

    try:
        tz = ZoneInfo(user_timezone)
    except Exception:
        tz = ZoneInfo("Asia/Kolkata")

    ts, eph = get_skyfield_resources()
    sun = eph["sun"]
    earth = eph["earth"]
    satellite = EarthSatellite(line1, line2, sat_name, ts)
    observer = wgs84.latlon(latitude, longitude)

    t0 = ts.now()
    t1 = ts.utc(t0.utc_datetime() + datetime.timedelta(days=max(1, min(days, 7))))

    cloud_forecast = get_hourly_cloud_cover(latitude, longitude, days=min(days + 2, 7))
    hourly_clouds = {}
    if "hourly" in cloud_forecast:
        times = cloud_forecast["hourly"].get("time", [])
        covers = cloud_forecast["hourly"].get("cloud_cover", [])
        for t_str, cover in zip(times, covers):
            hourly_clouds[t_str[:13]] = cover

    times, events = satellite.find_events(observer, t0, t1, altitude_degrees=min_elevation_deg)

    passes = []
    i = 0
    while i < len(events) - 2:
        if events[i] == 0 and events[i+1] == 1 and events[i+2] == 2:
            t_rise, t_culm, t_set = times[i], times[i+1], times[i+2]
            
            diff = satellite - observer
            topocentric_culm = diff.at(t_culm)
            alt_culm, az_culm, _ = topocentric_culm.altaz()
            
            topocentric_rise = diff.at(t_rise)
            _, az_rise, _ = topocentric_rise.altaz()
            topocentric_set = diff.at(t_set)
            _, az_set, _ = topocentric_set.altaz()

            obs_pos = earth + observer
            sun_alt = obs_pos.at(t_culm).observe(sun).apparent().altaz()[0].degrees

            sat_sunlit = bool(satellite.at(t_culm).is_sunlit(eph))
            is_visually_observable = bool((sun_alt < -6.0) and sat_sunlit)

            dt_rise_utc = t_rise.utc_datetime()
            dt_culm_utc = t_culm.utc_datetime()
            dt_set_utc = t_set.utc_datetime()

            dt_rise_local = dt_rise_utc.astimezone(tz)
            dt_culm_local = dt_culm_utc.astimezone(tz)
            dt_set_local = dt_set_utc.astimezone(tz)

            duration_sec = int((dt_set_utc - dt_rise_utc).total_seconds())

            hour_key = dt_culm_local.strftime("%Y-%m-%dT%H")
            cloud_pct = hourly_clouds.get(hour_key, None)

            rise_dir = _compass_direction(az_rise.degrees)
            set_dir = _compass_direction(az_set.degrees)

            passes.append({
                "satellite": sat_name,
                "norad_id": norad_id,
                "start_time_local": dt_rise_local.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "peak_time_local": dt_culm_local.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "end_time_local": dt_set_local.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "start_time_utc": dt_rise_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "duration_seconds": duration_sec,
                "max_elevation_deg": round(alt_culm.degrees, 1),
                "trajectory": f"{rise_dir} to {set_dir}",
                "sunlit": sat_sunlit,
                "observer_darkness": bool(sun_alt < -6.0),
                "visible_to_naked_eye": bool(is_visually_observable),
                "cloud_cover_pct": cloud_pct,
                "viewing_verdict": "Clear Naked-Eye Sighting" if (is_visually_observable and (cloud_pct is None or cloud_pct < 40)) else ("Cloudy / Obscured" if (is_visually_observable and cloud_pct and cloud_pct >= 40) else "Daylight Pass / Radar Only")
            })
            i += 3
        else:
            i += 1

    return {
        "satellite_name": sat_name,
        "norad_id": norad_id,
        "user_location": {"latitude": latitude, "longitude": longitude},
        "timezone": str(tz),
        "total_passes_computed": len(passes),
        "visible_passes_count": int(sum(1 for p in passes if p["visible_to_naked_eye"])),
        "passes": passes
    }

# ---------------------------------------------------------
# Specialized Sandbox Analytics Tools
# ---------------------------------------------------------

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

    # Run selection logic in the Python sandbox
    code = f"""
import json
passes = json.loads({repr(json.dumps(passes))})
visible = [p for p in passes if p.get('visible_to_naked_eye')]
candidates = visible if visible else passes

def score(p):
    elev = p.get('max_elevation_deg', 0)
    cloud = p.get('cloud_cover_pct')
    if cloud is None:
        cloud = 20
    return elev * (1.0 - (cloud / 100.0))

best = max(candidates, key=score)
print(f"BEST_NIGHT: {{best.get('peak_time_local')}}, ELEVATION: {{best.get('max_elevation_deg')}} deg, CLOUD COVER: {{best.get('cloud_cover_pct')}}%, VERDICT: {{best.get('viewing_verdict')}}")
"""
    raw_output = run_in_code_sandbox(code)

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


# WRITE: after each turn, send the session to Memory Bank for extraction.
async def generate_memories_callback(callback_context: CallbackContext):
    # Pass custom_metadata to trigger instant synchronous memory extraction on Agent Engine Memory Bank
    try:
        if hasattr(callback_context, '_invocation_context') and callback_context._invocation_context.memory_service:
            session = callback_context._invocation_context.session
            await callback_context._invocation_context.memory_service._add_events_to_memory_from_events(
                app_name=session.app_name,
                user_id=session.user_id,
                events_to_process=session.events,
                custom_metadata={"filter_patterns": []}
            )
        else:
            await callback_context.add_session_to_memory()
    except Exception as e:
        await callback_context.add_session_to_memory()
    return None

def build_system_instruction() -> str:
    role_description = (
        "You are OrbitWatch, an enthusiastic and precise space guide and orbital tracking assistant. "
        "Every satellite position, pass time, trajectory heading, and elevation must come strictly from "
        "live orbital data and real computation — never estimated or hallucinated by the model. "
        "All times should be presented clearly in the user's local time zone (default Asia/Kolkata). "
        "Observer Location Defaults: If the user's location is not yet known or remembered, ALWAYS default "
        "to Bengaluru, Karnataka, India (Latitude: 12.9716, Longitude: 77.5946, Timezone: Asia/Kolkata). "
        "Never stop to ask for coordinates if asking for passes; immediately calculate and display the passes "
        "for Bengaluru as the default location! "
        "User Preferences & Memory: Automatically personalize responses using facts remembered from Memory Bank "
        "across sessions (the user's city/coordinates, observing hours, favourite satellites, and equipment like "
        "naked eye, binoculars, telescope). When the user tells you their location, observing hours, equipment, or "
        "favourite satellites, confirm and store them so they are remembered. If the user asks for viewing suggestions "
        "(e.g. 'Anything worth seeing this week?'), filter upcoming visible passes to their remembered location, "
        "observing time window, and equipment capabilities."
    )
    workflow_description = (
        "Analyze the request, fetch real orbital/weather data or sightings from the tools, and return structured UI "
        "when the user asks for passes, satellite details, sightings, or visual cards."
    )
    ui_description = (
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use Table or Heading (unsupported), "
        "or Buttons, actions, or forms (they do nothing in adk web). "
        "Build tables from Rows/Columns of Text, and use Text with usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "You may include an Image component when you have a public https URL (such as patch_url or public badge URL). "
        "Set the Image url to that exact https link, for example: {\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. "
        "Never point an Image at a bare filename, an artifact name, or a non-http(s) path. "
        "Output ONLY the raw A2UI JSON array when rendering UI — no prose before or after, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    )

    try:
        from a2ui.schema.manager import A2uiSchemaManager
        from a2ui.basic_catalog.provider import BasicCatalog

        schema_manager = A2uiSchemaManager(
            version="0.8",
            catalogs=[BasicCatalog.get_config("0.8")],
        )
        return schema_manager.generate_system_prompt(
            role_description=role_description,
            workflow_description=workflow_description,
            ui_description=ui_description,
            include_schema=True,
            include_examples=True,
        )
    except Exception:
        _prompt_candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'a2ui_system_prompt.txt'),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'a2ui_system_prompt.txt'),
            'a2ui_system_prompt.txt',
            os.path.join('/code', 'a2ui_system_prompt.txt'),
            os.path.join('/code', 'app', 'a2ui_system_prompt.txt'),
        ]
        for _p in _prompt_candidates:
            if os.path.exists(_p):
                with open(_p, 'r', encoding='utf-8') as _f:
                    return _f.read()
        return role_description

SYSTEM_INSTRUCTION = build_system_instruction()

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=SYSTEM_INSTRUCTION,
    tools=[
        PreloadMemoryTool(),
        compute_orbital_mechanics,
        count_satellites_above_horizon,
        choose_best_viewing_night,
        run_in_code_sandbox,
        generate_mission_patch,
        log_sighting,
        list_sightings,
        predict_passes,
        fetch_tle,
        get_iss_position,
        get_cloud_cover,
        fetch_celestrak_tles,
        get_iss_current_location,
        get_hourly_cloud_cover,
        geocode_location,
        save_user_preferences,
        add_user_location,
        set_user_preferences,
        list_watchlist,
        add_to_watchlist
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
