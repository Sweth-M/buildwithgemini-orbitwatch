import asyncio
from dotenv import load_dotenv
load_dotenv()

from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.code_executors.base_code_executor import CodeExecutionInput
from unittest.mock import MagicMock

sandbox = AgentEngineSandboxCodeExecutor(agent_engine_resource_name='projects/698694960991/locations/us-east1/reasoningEngines/2926440357279301632')

mock_context = MagicMock()
mock_context.session.state = {}

async def test():
    inp = CodeExecutionInput(code='print(12345 * 67890)')
    res = await sandbox.execute_code(mock_context, inp)
    print('Outcome:', res.outcome)
    print('Output:', res.output)
    print('Created sandbox name:', mock_context.session.state.get('sandbox_name'))

asyncio.run(test())
