import re

with open("app/agent.py") as f:
    content = f.read()

target = """    try:
        with httpx.Client(timeout=10.0) as client:"""

replacement = """    # If local cached file for NORAD ID exists, load it
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

    try:
        with httpx.Client(timeout=10.0) as client:"""

if target in content:
    content = content.replace(target, replacement, 1)
    with open("app/agent.py", "w") as f:
        f.write(content)
    print("Patched app/agent.py successfully!")
else:
    print("Target not found!")
