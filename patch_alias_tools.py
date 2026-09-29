with open("app/agent.py") as f:
    code = f.read()

aliases = '''
def add_user_location(location_name: str, latitude: Optional[float] = None, longitude: Optional[float] = None) -> Dict[str, Any]:
    """Alias to save user location."""
    return save_user_preferences(location_name=location_name, latitude=latitude or 12.9716, longitude=longitude or 77.5946)

def set_user_preferences(observing_hours: Optional[str] = None, equipment: Optional[str] = None, location_name: Optional[str] = None) -> Dict[str, Any]:
    """Alias to set user observing preferences."""
    return save_user_preferences(
        location_name=location_name or "Bengaluru",
        observing_hours=observing_hours or "7 PM to 10 PM",
        equipment=equipment or "binoculars"
    )
'''

if "def add_user_location" not in code:
    code = code.replace("def save_user_preferences", aliases + "\ndef save_user_preferences")
    code = code.replace("save_user_preferences,", "save_user_preferences,\n        add_user_location,\n        set_user_preferences,")
    with open("app/agent.py", "w") as f:
        f.write(code)
    print("Added aliases to app/agent.py")
else:
    print("Aliases already present")
