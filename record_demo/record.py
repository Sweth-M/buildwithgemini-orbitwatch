import os
import time
from playwright.sync_api import sync_playwright

output_dir = "record_demo/raw_video"
os.makedirs(output_dir, exist_ok=True)

frontend_url = "http://localhost:8080"

print(f"Launching browser to record demo against {frontend_url}...")

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        executable_path="/usr/bin/google-chrome",
        args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
    )
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        record_video_dir=output_dir,
        record_video_size={"width": 1280, "height": 800}
    )
    page = context.new_page()

    page.goto(frontend_url, wait_until="networkidle")
    time.sleep(2.0)  # Let stars and interface settle

    # First turn: Where is the ISS right now?
    prompt1 = "Where is the ISS right now?"
    print(f"Turn 1: {prompt1}")
    page.fill("#input", prompt1)
    time.sleep(1.0)
    page.click("button[type='submit']")

    # Wait for the first agent reply bubble to complete (not showing scanning placeholder)
    page.wait_for_function(
        """() => {
            const bubbles = document.querySelectorAll('.msg.agent .bubble');
            if (bubbles.length === 0) return false;
            const last = bubbles[bubbles.length - 1];
            return last && !last.textContent.includes('Scanning skies…') && last.textContent.trim().length > 10;
        }""",
        timeout=30000
    )
    print("Turn 1 response received.")
    time.sleep(3.0)  # Pause to showcase first response

    # Second turn: Show upcoming ISS passes over Bengaluru this week as a table, then log tonight's best pass as a sighting and show its mission patch in a card.
    prompt2 = "Show upcoming ISS passes over Bengaluru this week as a table, then log tonight's best pass as a sighting and show its mission patch in a card."
    print(f"Turn 2: {prompt2}")
    page.fill("#input", prompt2)
    time.sleep(1.0)
    page.click("button[type='submit']")

    print("Waiting 30000 ms for turn 2...")
    # User requested: "Use a wait of 30000 for the second turn"
    page.wait_for_timeout(30000)

    print("Turn 2 finished. Adding final showcase pause...")
    time.sleep(3.0)

    context.close()
    video_path = page.video.path()
    browser.close()
    print("Recording complete! Video saved at:", video_path)

    with open("record_demo/video_path.txt", "w") as f:
        f.write(video_path)
