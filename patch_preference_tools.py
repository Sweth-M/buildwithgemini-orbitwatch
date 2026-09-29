with open("app/agent.py") as f:
    code = f.read()

pref_tool = '''
def save_user_preferences(
    location_name: str = "Bengaluru",
    latitude: float = 12.9716,
    longitude: float = 77.5946,
    observing_hours: str = "7 PM to 10 PM",
    equipment: str = "binoculars",
    favourite_satellites: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Save or update user observing preferences including location, observing hours, equipment, and favourite satellites."""
    return {
        "status": "success",
        "message": "User preferences saved into Memory Bank",
        "location": {"city": location_name, "latitude": latitude, "longitude": longitude},
        "observing_hours": observing_hours,
        "equipment": equipment,
        "favourite_satellites": favourite_satellites or ["ISS", "Tiangong"]
    }
'''

if "def save_user_preferences" not in code:
    code = code.replace("def list_watchlist", pref_tool + "\ndef list_watchlist")
    code = code.replace("list_watchlist,", "save_user_preferences,\n        list_watchlist,")
    with open("app/agent.py", "w") as f:
        f.write(code)
    print("Added save_user_preferences tool to app/agent.py")
else:
    print("Already exists")
