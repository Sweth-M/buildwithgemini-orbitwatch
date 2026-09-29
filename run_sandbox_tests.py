import asyncio
from dotenv import load_dotenv
load_dotenv()

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from app.agent import root_agent
from google.genai import types

async def run_all_tests():
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    runner = Runner(
        agent=root_agent,
        session_service=session_service,
        artifact_service=artifact_service,
        app_name='orbitwatch'
    )
    session = await session_service.create_session(app_name='orbitwatch', user_id='stargazer')

    tests = [
        "What are the ISS's orbital period and altitude?",
        "How many Starlink satellites are above Bengaluru's horizon right now?",
        "Which night this week is best for seeing the ISS?"
    ]

    for prompt in tests:
        print(f"\n==================== TEST: {prompt} ====================")
        content = types.Content(role='user', parts=[types.Part.from_text(text=prompt)])
        async for event in runner.run_async(session_id=session.id, user_id='stargazer', new_message=content):
            if hasattr(event, 'content') and event.content:
                for part in event.content.parts:
                    if getattr(part, 'text', None):
                        print(part.text, end='', flush=True)
                    if getattr(part, 'function_call', None):
                        print(f"\n[Tool Call]: {part.function_call.name}({part.function_call.args})")
                    if getattr(part, 'function_response', None):
                        print(f"\n[Tool Response ({part.function_response.name})]: {part.function_response.response}")
        print()

asyncio.run(run_all_tests())
