import httpx

url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=tle"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
resp = httpx.get(url, headers=headers, timeout=15.0)
print("Status:", resp.status_code)
lines = [l.strip() for l in resp.text.splitlines() if l.strip()]
print("Lines:", len(lines))
if len(lines) > 10:
    with open("starlink_tles.txt", "w") as f:
        f.write(resp.text)
    print("Saved starlink_tles.txt successfully!")
