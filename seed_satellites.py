import sys
from google.cloud import firestore

GCP_PROJECT_ID = "qwiklabs-gcp-04-e954671c3d10"

SEED_SATELLITES = [
    {
        "norad_id": 25544,
        "name": "International Space Station",
        "category": "station",
        "description": "The largest modular space station in low Earth orbit, continuously occupied since November 2000.",
        "patch_url": "https://storage.googleapis.com/orbitwatch-badges-fdf4c252/iss_patch.png"
    },
    {
        "norad_id": 48274,
        "name": "Tiangong Space Station",
        "category": "station",
        "description": "China's permanent space station in low Earth orbit (Tianhe core module launched in 2021).",
        "patch_url": "https://storage.googleapis.com/orbitwatch-badges-fdf4c252/tiangong_patch.png"
    },
    {
        "norad_id": 20580,
        "name": "Hubble Space Telescope",
        "category": "telescope",
        "description": "Legendary space telescope launched into low Earth orbit in 1990 by Space Shuttle Discovery.",
        "patch_url": "https://storage.googleapis.com/orbitwatch-badges-fdf4c252/hubble_patch.png"
    },
    {
        "norad_id": 33591,
        "name": "NOAA 19",
        "category": "weather",
        "description": "Polar-orbiting operational environmental satellite operated by NOAA providing global weather imagery.",
        "patch_url": "https://storage.googleapis.com/orbitwatch-badges-fdf4c252/noaa19_patch.png"
    },
    {
        "norad_id": 25994,
        "name": "Terra",
        "category": "earth_observation",
        "description": "NASA flagship Earth-observing satellite carrying MODIS and ASTER instruments.",
        "patch_url": "https://storage.googleapis.com/orbitwatch-badges-fdf4c252/terra_patch.png"
    }
]

def seed_firestore():
    print(f"Connecting to Firestore for project '{GCP_PROJECT_ID}'...")
    db = firestore.Client(project=GCP_PROJECT_ID)
    collection = db.collection("orbit_satellites")

    for sat in SEED_SATELLITES:
        doc_id = str(sat["norad_id"])
        print(f"Seeding satellite {sat['name']} (NORAD {sat['norad_id']})...")
        collection.document(doc_id).set(sat)

    print(f"Successfully seeded {len(SEED_SATELLITES)} satellites into collection 'orbit_satellites'.")

if __name__ == "__main__":
    seed_firestore()
