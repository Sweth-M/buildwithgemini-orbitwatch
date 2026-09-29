import asyncio
from dotenv import load_dotenv
load_dotenv()

from google.adk.memory import VertexAiMemoryBankService
from google.adk.sessions import Session
from google.adk.events import Event
from google.genai import types

async def test():
    svc = VertexAiMemoryBankService(
        project="qwiklabs-gcp-04-e954671c3d10",
        location="us-east1",
        agent_engine_id="2926440357279301632",
    )
    
    session = Session(id="s1", app_name="orbitwatch", user_id="test_stargazer")
    ev1 = Event(
        author="user",
        content=types.Content(role="user", parts=[types.Part.from_text(text="I live in Bengaluru, I can only observe between 7 and 10 PM, and I have binoculars.")])
    )
    ev2 = Event(
        author="model",
        content=types.Content(role="model", parts=[types.Part.from_text(text="Understood! I will remember your location in Bengaluru, your 7 to 10 PM observing window, and your binoculars equipment.")])
    )
    session.events.extend([ev1, ev2])

    print("Generating memory explicitly...")
    await svc._add_events_to_memory_from_events(
        app_name="orbitwatch",
        user_id="test_stargazer",
        events_to_process=session.events,
        custom_metadata={"filter_patterns": []} # forces _should_use_generate_memories to True!
    )
    print("Memory generation completed!")

    print("\nWaiting 5 seconds and searching memory...")
    await asyncio.sleep(5)
    res = await svc.search_memory(user_id="test_stargazer", app_name="orbitwatch", query="observing equipment location")
    print("Found memories:", res.memories)

asyncio.run(test())
