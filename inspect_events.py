import asyncio
from dotenv import load_dotenv
load_dotenv()

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from app.agent import root_agent
from google.genai import types

async def test():
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    runner = Runner(agent=root_agent, session_service=session_service, artifact_service=artifact_service, app_name='orbitwatch')
    session = await session_service.create_session(app_name='orbitwatch', user_id='stargazer')

    prompt = "What are the ISS's orbital period and altitude?"
    print(f"=== TEST: {prompt} ===")
    content = types.Content(role='user', parts=[types.Part.from_text(text=prompt)])
    async for event in runner.run_async(session_id=session.id, user_id='stargazer', new_message=content):
        print(f"\n[EVENT] author={getattr(event, 'author', None)} type={type(event)}")
        if hasattr(event, 'content') and event.content:
            for p in event.content.parts:
                print(" PART:", {k: v for k, v in p.__dict__.items() if v is not None})

asyncio.run(test())
