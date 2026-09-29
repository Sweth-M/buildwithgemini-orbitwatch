import asyncio
import os
import time
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )
        
        os.makedirs("demo_recordings", exist_ok=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir="demo_recordings/",
            record_video_size={"width": 1280, "height": 800}
        )
        
        page = await context.new_page()
        print("Navigating to http://127.0.0.1:8090/...")
        await page.goto("http://127.0.0.1:8090/")
        await page.wait_for_selector("#form")
        await asyncio.sleep(2)
        
        # Turn 1: "Where is the ISS right now?"
        print("Submitting Turn 1: Where is the ISS right now?")
        input_el = page.locator("#input")
        await input_el.fill("Where is the ISS right now?")
        await asyncio.sleep(1)
        await page.locator("#send-btn").click()
        
        # Wait for Turn 1 response
        print("Waiting for Turn 1 response...")
        await page.wait_for_selector("#input:not([disabled])", timeout=60000)
        print("Turn 1 response rendered!")
        await asyncio.sleep(4)
        
        # Turn 2: "Show upcoming ISS passes over Bengaluru this week as a table, then log tonight's best pass as a sighting and show its mission patch in a card."
        prompt_2 = "Show upcoming ISS passes over Bengaluru this week as a table, then log tonight's best pass as a sighting and show its mission patch in a card."
        print(f"Submitting Turn 2: {prompt_2}")
        await input_el.fill(prompt_2)
        await asyncio.sleep(1)
        await page.locator("#send-btn").click()
        
        # User explicitly requested: "Use a wait of 30000"
        print("Waiting 30 seconds (30000ms) as requested...")
        await asyncio.sleep(30)
        
        # Wait up to 60 additional seconds if needed for A2UI card & mission patch image
        try:
            await page.wait_for_selector("#input:not([disabled])", timeout=60000)
            print("Turn 2 response completed!")
        except Exception as e:
            print(f"Selector note: {e}")
            
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
        await asyncio.sleep(6)
        
        await context.close()
        await browser.close()
        print("Demo recorded successfully.")

if __name__ == "__main__":
    asyncio.run(run())
