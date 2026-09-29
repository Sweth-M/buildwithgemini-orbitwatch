import asyncio
from dotenv import load_dotenv
load_dotenv()

from google.adk.agents import Agent
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

AGENT_ENGINE_RESOURCE = "projects/698694960991/locations/us-east1/reasoningEngines/2926440357279301632"

sandbox_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=AGENT_ENGINE_RESOURCE
)

agent = Agent(
    name="test_sandbox_agent",
    model=Gemini(model="gemini-2.5-flash"),
    instruction="You can run python code in the sandbox to calculate things.",
    code_executor=sandbox_executor,
)

async def test():
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, session_service=session_service, app_name='test')
    session = await session_service.create_session(app_name='test', user_id='stargazer')
    content = types.Content(role='user', parts=[types.Part.from_text(text="Calculate 12345 * 67890 in python.")])
    
    async for event in runner.run_async(session_id=session.id, user_id='stargazer', new_message=content):
        print("Event:", type(event), event)

asyncio.run(test())
