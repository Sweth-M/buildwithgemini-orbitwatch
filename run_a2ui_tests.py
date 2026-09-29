import asyncio
import json
from dotenv import load_dotenv
load_dotenv()

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory import VertexAiMemoryBankService
from app.agent import root_agent
from google.genai import types

PROJECT_ID = "qwiklabs-gcp-04-e954671c3d10"
LOCATION = "us-east1"
MEMORY_BANK_ID = "2926440357279301632"

async def test_a2ui(prompt: str):
    print(f"\n==================== TEST: {prompt} ====================")
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    memory_service = VertexAiMemoryBankService(
        project=PROJECT_ID,
        location=LOCATION,
        agent_engine_id=MEMORY_BANK_ID,
    )

    runner = Runner(
        agent=root_agent,
        session_service=session_service,
        artifact_service=artifact_service,
        memory_service=memory_service,
        app_name="orbitwatch"
    )

    session = await session_service.create_session(app_name="orbitwatch", user_id="stargazer")
    content = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])

    async for event in runner.run_async(session_id=session.id, user_id="stargazer", new_message=content):
        if hasattr(event, 'content') and event.content:
            for p in event.content.parts:
                if getattr(p, 'text', None):
                    print(p.text)
                elif getattr(p, 'inline_data', None):
                    data = p.inline_data.data
                    print("\n[A2UI Inline Data Part Detected]:")
                    if isinstance(data, bytes):
                        text = data.decode("utf-8")
                        print(text[:300] + ("..." if len(text) > 300 else ""))
                if getattr(p, 'function_call', None):
                    print(f"\n[Tool Call]: {p.function_call.name}({p.function_call.args})")

async def main():
    await test_a2ui("Show upcoming ISS and Tiangong passes as a table.")
    await test_a2ui("Show me a card for the ISS.")
    await test_a2ui("Show my sightings log.")

asyncio.run(main())
