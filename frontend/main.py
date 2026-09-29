from dotenv import load_dotenv
load_dotenv("/config/Desktop/BuildWithGemini/orbitwatch/.env")
load_dotenv()
"""Standalone FastAPI local proxy & web chat UI for OrbitWatch."""

import os
import sys
import uuid
import asyncio
from typing import Dict, Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# Add agent path to sys.path
sys.path.insert(0, "/config/Desktop/BuildWithGemini/orbitwatch")
from app.agent import root_agent
from app.app_utils import services
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types

app = FastAPI(title="OrbitWatch UI")

session_service = InMemorySessionService()
artifact_service = InMemoryArtifactService()
memory_service = services.get_memory_service()

runner = Runner(
    agent=root_agent,
    session_service=session_service,
    artifact_service=artifact_service,
    memory_service=memory_service,
    app_name="orbitwatch"
)

# Cache sessions by ID
active_sessions = {}

@app.post("/chat")
async def chat(request: Request):
    payload = await request.json()
    user_msg = payload.get("message", "").strip()
    session_id = payload.get("session_id") or str(uuid.uuid4())

    if not user_msg:
        return JSONResponse({
            "parts": [{"kind": "text", "text": "Please ask an orbital or satellite-tracking question."}],
            "session_id": session_id
        })

    try:
        if session_id not in active_sessions:
            session = await session_service.create_session(
                app_name="orbitwatch",
                user_id="stargazer",
                session_id=session_id
            )
            active_sessions[session_id] = session
        else:
            session = active_sessions[session_id]

        content = types.Content(role="user", parts=[types.Part.from_text(text=user_msg)])
        parts = []

        async for event in runner.run_async(session_id=session.id, user_id="stargazer", new_message=content):
            if hasattr(event, "content") and event.content:
                for p in event.content.parts:
                    if getattr(p, "text", None):
                        parts.append({"kind": "text", "text": p.text})
                    elif getattr(p, "inline_data", None):
                        data = p.inline_data.data
                        if isinstance(data, bytes):
                            text = data.decode("utf-8")
                        else:
                            text = str(data)
                        
                        import json
                        import re
                        # Clean tag if present
                        m = re.search(r'<a2a_datapart_json>(.*?)</a2a_datapart_json>', text, re.DOTALL)
                        if m:
                            text = m.group(1).strip()
                        try:
                            parsed = json.loads(text)
                            if "data" in parsed:
                                parts.append({"kind": "a2ui", "data": parsed["data"]})
                            else:
                                parts.append({"kind": "a2ui", "data": parsed})
                        except Exception:
                            parts.append({"kind": "text", "text": text})

        return JSONResponse({
            "parts": parts if parts else [{"kind": "text", "text": "Observation complete."}],
            "session_id": session_id
        })
    except Exception as e:
        return JSONResponse({
            "parts": [{"kind": "text", "text": f"Error tracking satellite: {str(e)}"}],
            "session_id": session_id
        }, status_code=500)

app.mount("/", StaticFiles(directory="/config/Desktop/BuildWithGemini/frontend/static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8090)
