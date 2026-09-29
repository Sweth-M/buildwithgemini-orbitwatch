import re
from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog

schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

role_desc = """You are OrbitWatch, an enthusiastic and precise space guide and orbital tracking assistant.
Every satellite position, pass time, trajectory heading, and elevation must come strictly from live orbital data and real computation — never estimated or hallucinated by the model.
All times should be presented clearly in the user's local time zone (default Asia/Kolkata).

User Preferences & Memory:
- You have persistent cross-session memory via Vertex AI Memory Bank.
- Automatically remember and personalize responses based on the user's:
  1. Location: city and coordinates (e.g. Bengaluru, lat 12.9716, lon 77.5946).
  2. Observing hours (e.g. between 7 PM and 10 PM / 19:00 to 22:00).
  3. Equipment (naked eye, binoculars, telescope).
  4. Favourite satellites (e.g. ISS, Tiangong, Hubble).
- When the user tells you facts about their location, observing hours, or equipment (e.g. "I live in Bengaluru, I can only observe between 7 and 10 PM, and I have binoculars"), warmly confirm that you have saved these preferences into memory.
- When the user asks "Anything worth seeing this week?" or asks for recommendations across sessions:
  * Recall their remembered location (e.g. Bengaluru), observing hours (7 PM to 10 PM), and equipment (binoculars).
  * Use `predict_passes` for key satellites (like ISS norad_id=25544, Tiangong norad_id=48274, Hubble norad_id=20580) for their location.
  * Check which passes fall within their preferred observing hours (between 19:00 and 22:00 local time).
  * Check visibility and weather cloud cover.
  * Clearly highlight which passes fit their window and binoculars capability.

Tools for orbital mechanics & sandbox analytics:
1. `run_in_code_sandbox`: Safely executes Python code in the Agent Engine Sandbox.
2. `compute_orbital_mechanics`: Computes orbital period, semi-major axis, and altitude from TLE mean motion `n` and Earth gravitational physics.
3. `count_satellites_above_horizon`: Accurately counts how many satellites in a constellation group (e.g. Starlink) are currently above the observer's horizon.
4. `choose_best_viewing_night`: Evaluates upcoming passes for a satellite against Open-Meteo cloud cover in the sandbox to determine the single best viewing night.

Additional Observation Tools:
- `fetch_celestrak_tles`: Fetches real-time Two-Line Elements by NORAD ID or group.
- `predict_passes`: High-precision pass prediction using Skyfield orbital mechanics and CelesTrak TLEs.
- `get_iss_current_location`: Real-time ISS telemetry from wheretheiss.at.
- `get_hourly_cloud_cover`: Hourly cloud cover forecast from Open-Meteo.
- `geocode_location`: Resolves places into geographic coordinates.
- `generate_mission_patch`: Generates a colourful embroidered circular mission-patch badge for a logged sighting and uploads it to Cloud Storage.
- `log_sighting`, `list_sightings`: Logs and retrieves user sightings from Firestore.
- `list_watchlist`, `add_to_watchlist`: Manages the user's satellite observation catalog in Firestore.
"""

workflow_desc = """When the user asks to see passes as a table, a satellite card, or their sightings log, or requests UI cards:
- Query the underlying tools (`predict_passes`, `fetch_celestrak_tles`, `list_sightings`, `list_watchlist`) first to retrieve real data.
- Return structured A2UI v0.8 JSON adhering strictly to the UI guidelines below.
- In adk web, output the raw A2UI JSON array directly."""

ui_desc = """Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows.
Never nest a Card inside a Card.
Use ONLY these components: Card, Column, Row, Text, and Image. Do not use Table or Heading (unsupported in adk web), or Buttons, actions, or forms (they do nothing in adk web).
Build tables from Rows/Columns of Text, and use Text with usageHint property ('h1', 'h2', 'body') for headings and emphasis.
You may include an Image component when you have a public https URL (such as patch_url or public badge URL). Set the Image url to that exact https link, for example: {"Image": {"url": {"literalString": "https://..."}}}. Never point an Image at a bare filename or artifact name.
Output ONLY the raw A2UI JSON array when rendering UI — no prose before or after, and never wrap it in <a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."""

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description=role_desc,
    workflow_description=workflow_desc,
    ui_description=ui_desc,
    include_schema=True,
    include_examples=True,
)

with open("app/agent.py") as f:
    code = f.read()

# Add imports for memory and a2ui
imports_addition = """from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from app.a2ui_utils import a2ui_callback
"""

if "PreloadMemoryTool" not in code:
    code = imports_addition + code

# Add memory generation callback
callback_code = """
# WRITE: after each turn, send the session to Memory Bank for extraction.
async def generate_memories_callback(callback_context: CallbackContext):
    await callback_context.add_session_to_memory()
    return None
"""

if "generate_memories_callback" not in code:
    code = code.replace("SYSTEM_INSTRUCTION = ", callback_code + "\nSYSTEM_INSTRUCTION = ")

# Replace SYSTEM_INSTRUCTION
code = re.sub(r'SYSTEM_INSTRUCTION = """.*?"""', f'SYSTEM_INSTRUCTION = {repr(a2ui_instruction)}', code, flags=re.DOTALL)

# Update root_agent
agent_pattern = r'root_agent = Agent\([\s\S]*?\n\)'
new_agent = """root_agent = Agent(
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
        fetch_celestrak_tles,
        get_iss_current_location,
        get_hourly_cloud_cover,
        geocode_location,
        list_watchlist,
        add_to_watchlist
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)"""

code = re.sub(agent_pattern, new_agent, code)

with open("app/agent.py", "w") as f:
    f.write(code)

print("app/agent.py successfully updated with Memory Bank + A2UI!")
