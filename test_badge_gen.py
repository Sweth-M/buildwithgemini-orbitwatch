import asyncio
from google import genai
from google.cloud import storage
import uuid

GCP_PROJECT_ID = "qwiklabs-gcp-04-e954671c3d10"
STORAGE_BUCKET_NAME = "orbitwatch-badges-fdf4c252"

async def generate_mission_patch(satellite_name: str, location_name: str, date_str: str) -> str:
    genai_client = genai.Client(vertexai=True, project=GCP_PROJECT_ID, location="global")
    prompt = (
        f"A colourful, vintage embroidered circular mission-patch style badge celebrating a satellite sighting. "
        f"In the center, a bold silhouette of the satellite ({satellite_name}) soaring through a dark navy night sky with stars and orbital trajectory arcs. "
        f"The circular border features embroidered text: '{satellite_name.upper()}' at the top, and '{location_name.upper()} • {date_str}' along the bottom edge. "
        "Rich embroidered fabric textures, sharp stitching detail, vivid space badge illustration."
    )
    
    response = genai_client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=prompt
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
        raise ValueError("Failed to get image bytes")
        
    filename = f"patch_{uuid.uuid4().hex[:8]}.jpg"
    storage_client = storage.Client(project=GCP_PROJECT_ID)
    bucket = storage_client.bucket(STORAGE_BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(image_bytes, content_type=mime_type)
    
    public_url = f"https://storage.googleapis.com/{STORAGE_BUCKET_NAME}/{filename}"
    print("Uploaded patch URL:", public_url)
    return public_url

asyncio.run(generate_mission_patch("ISS", "Bengaluru", "2026-09-29"))
