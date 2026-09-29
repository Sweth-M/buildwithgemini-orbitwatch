from google.adk.memory import VertexAiMemoryBankService

try:
    svc = VertexAiMemoryBankService(
        project="qwiklabs-gcp-04-e954671c3d10",
        location="us-east1",
        agent_engine_id="2926440357279301632"
    )
    print("Initialized VertexAiMemoryBankService:", svc)
except Exception as e:
    print("Error:", e)
