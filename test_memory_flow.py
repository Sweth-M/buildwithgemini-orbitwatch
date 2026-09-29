import asyncio
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

async def test():
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

    user_id = "test_stargazer"
    
    # Session 1: State preferences
    print("=== SESSION 1: Stating preferences ===")
    session1 = await session_service.create_session(app_name="orbitwatch", user_id=user_id)
    prompt1 = "I live in Bengaluru, I can only observe between 7 and 10 PM, and I have binoculars."
    content1 = types.Content(role="user", parts=[types.Part.from_text(text=prompt1)])
    
    async for event in runner.run_async(session_id=session1.id, user_id=user_id, new_message=content1):
        if hasattr(event, 'content') and event.content:
            for p in event.content.parts:
                if getattr(p, 'text', None):
                    print(p.text, end='', flush=True)
    print("\n\nWaiting 10 seconds for Memory Bank background extraction...")
    await asyncio.sleep(10)

    # Session 2: New session! Ask "Anything worth seeing this week?"
    print("\n=== SESSION 2: Asking 'Anything worth seeing this week?' in a NEW session ===")
    session2 = await session_service.create_session(app_name="orbitwatch", user_id=user_id)
    prompt2 = "Anything worth seeing this week?"
    content2 = types.Content(role="user", parts=[types.Part.from_text(text=prompt2)])

    async for event in runner.run_async(session_id=session2.id, user_id=user_id, new_message=content2):
        if hasattr(event, 'content') and event.content:
            for p in event.content.parts:
                if getattr(p, 'text', None):
                    print(p.text, end='', flush=True)
                if getattr(p, 'function_call', None):
                    print(f"\n[Tool Call]: {p.function_call.name}({p.function_call.args})")
    print()

asyncio.run(test())
