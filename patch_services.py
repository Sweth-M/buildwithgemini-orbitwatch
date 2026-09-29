with open("app/app_utils/services.py") as f:
    code = f.read()

addition = """
MEMORY_SERVICE_URI = "shared://memory"

@functools.cache
def get_memory_service():
    \"\"\"Process-wide Vertex AI Memory Bank service.\"\"\"
    from google.adk.memory import VertexAiMemoryBankService
    return VertexAiMemoryBankService(
        project="qwiklabs-gcp-04-e954671c3d10",
        location="us-east1",
        agent_engine_id="2926440357279301632",
    )

"""

if "def get_memory_service" not in code:
    code = code.replace('@functools.cache\ndef get_artifact_service():', addition + '@functools.cache\ndef get_artifact_service():')
    code += '\n_registry.register_memory_service("shared", lambda uri, **kw: get_memory_service())\n'
    with open("app/app_utils/services.py", "w") as f:
        f.write(code)
    print("Patched services.py with get_memory_service")
else:
    print("Already patched services.py")
