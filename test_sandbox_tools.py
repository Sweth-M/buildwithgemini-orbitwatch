from dotenv import load_dotenv
load_dotenv()

from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.code_executors.base_code_executor import CodeExecutionInput
from unittest.mock import MagicMock

AGENT_ENGINE_RESOURCE = "projects/698694960991/locations/us-east1/reasoningEngines/2926440357279301632"
sandbox_executor = AgentEngineSandboxCodeExecutor(agent_engine_resource_name=AGENT_ENGINE_RESOURCE)
mock_context = MagicMock()
mock_context.session.state = {}

def execute_in_sandbox(python_code: str) -> str:
    """Execute Python code in the Agent Engine Python Sandbox and return stdout and stderr."""
    inp = CodeExecutionInput(code=python_code)
    res = sandbox_executor.execute_code(mock_context, inp)
    output = ""
    if res.stdout:
        output += res.stdout
    if res.stderr:
        output += ("\nError:\n" + res.stderr)
    return output.strip()

# Test 1: Orbital period and altitude from ISS TLE
code_test1 = """
import math
# ISS TLE line 2 mean motion n = 15.48685648
n = 15.48685648
mu = 398600.4418
earth_radius = 6378.137

period_min = 1440.0 / n
period_sec = period_min * 60.0
n_rad_sec = (n * 2 * math.pi) / 86400.0
a = (mu / (n_rad_sec ** 2)) ** (1.0 / 3.0)
altitude = a - earth_radius

print(f"Orbital Period: {period_min:.2f} minutes ({period_sec:.1f} seconds)")
print(f"Semi-major axis: {a:.2f} km")
print(f"Orbital Altitude: {altitude:.2f} km")
"""
print("=== Output Test 1 ===")
print(execute_in_sandbox(code_test1))
