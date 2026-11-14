"""Callside API: a lightweight call state and recap service."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Callside API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"], allow_headers=["*"],
)

STAGES = [
    {"id":"open", "name":"Open", "purpose":"Earn a few seconds and make the reason for calling clear.", "prompt":"Hi {{first_name}}, this is [your name] with [company]. Did I catch you with 30 seconds?", "signals":["Who is this?", "I have a minute", "What is this about?"], "tip":"Be direct. Ask for a small amount of time, then pause."},
    {"id":"permission", "name":"Permission", "purpose":"Confirm it is worth continuing before launching into a pitch.", "prompt":"I’m calling because we help [role] with [specific outcome]. Can I ask one quick question to see if it’s relevant?", "signals":["Sure, go ahead", "Make it quick", "Send me an email"], "tip":"Acknowledge their time. If they decline, ask when would be better."},
    {"id":"context", "name":"Context", "purpose":"Understand their role and how the current process works.", "prompt":"How are you handling [problem area] today?", "signals":["We use a spreadsheet", "Our team handles that", "It’s not really my area"], "tip":"Ask one question at a time. Let them finish before probing."},
    {"id":"discovery", "name":"Discovery", "purpose":"Find the friction, its impact, and whether it matters now.", "prompt":"What’s the most frustrating part of that? What happens when it slips?", "signals":["It takes too long", "We miss follow-ups", "It’s working fine"], "tip":"Follow their words. Look for a concrete example, not a checklist."},
    {"id":"impact", "name":"Impact", "purpose":"Make the cost or consequence of the problem tangible.", "prompt":"How often does that happen, and who else feels the impact?", "signals":["A few times a month", "My team spends hours on it", "It’s annoying but manageable"], "tip":"Quantify gently. Don’t manufacture urgency they haven’t expressed."},
    {"id":"fit", "name":"Fit", "purpose":"Connect the need to a relevant outcome and check for fit.", "prompt":"If you could [desired outcome], would that be useful enough to explore?", "signals":["Possibly", "How does it work?", "We already have a tool"], "tip":"Tie one capability to what they said. Avoid a feature dump."},
    {"id":"objections", "name":"Objections", "purpose":"Understand concerns and respond without arguing.", "prompt":"That makes sense. What would you need to see to feel comfortable taking a next step?", "signals":["We don’t have budget", "We’re under contract", "Just send information"], "tip":"Validate, clarify, then answer briefly. Respect a clear no."},
    {"id":"next_step", "name":"Next step", "purpose":"Agree on a specific, low-friction next action—or close gracefully.", "prompt":"Would a 20-minute look on Tuesday or Wednesday be useful?", "signals":["Tuesday works", "Email me first", "Not interested"], "tip":"Confirm owner, date, and purpose. Thank them either way."},
]

class StartCall(BaseModel):
    prospect: str = "New prospect"
    company: str = ""

class StageResult(BaseModel):
    stage_id: str
    outcome: str = "completed"
    prospect_words: str = ""

class CloseCall(BaseModel):
    outcome: str = "follow_up"
    notes: str = ""

calls: dict[str, dict[str, Any]] = {}

def persist(call: dict[str, Any]):
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        from supabase import create_client
        create_client(url, key).table("calls").upsert(call).execute()

def get_call(call_id: str):
    if call_id in calls:
        return calls[call_id]
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        from supabase import create_client
        rows = create_client(url, key).table("calls").select("*").eq("id", call_id).limit(1).execute().data
        if rows:
            calls[call_id] = rows[0]
            return calls[call_id]
    return None

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

@app.get("/health")
def health():
    return {"status":"ok", "service":"callside-api"}

@app.get("/api/stages")
def get_stages():
    return STAGES

@app.post("/api/calls")
def start_call(body: StartCall):
    call_id = str(uuid4())
    call = {"id":call_id, "prospect":body.prospect, "company":body.company, "current_stage":"open", "stage_results":[], "outcome":None, "notes":"", "started_at":utc_now(), "ended_at":None}
    calls[call_id] = call
    persist(call)
    return call

@app.get("/api/calls")
def list_calls():
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        try:
            from supabase import create_client
            return create_client(url, key).table("calls").select("*").order("started_at", desc=True).limit(100).execute().data
        except Exception:
            pass
    return sorted(calls.values(), key=lambda c: c["started_at"], reverse=True)

@app.post("/api/calls/{call_id}/stage")
def save_stage(call_id: str, body: StageResult):
    call = get_call(call_id)
    if not call: raise HTTPException(404, "Call not found")
    if body.stage_id not in {s["id"] for s in STAGES}: raise HTTPException(422, "Unknown stage")
    result = {**body.model_dump(), "saved_at":utc_now()}
    call["stage_results"] = [r for r in call["stage_results"] if r["stage_id"] != body.stage_id] + [result]
    idx = next(i for i, s in enumerate(STAGES) if s["id"] == body.stage_id)
    call["current_stage"] = STAGES[min(idx + 1, len(STAGES)-1)]["id"]
    persist(call)
    return call

@app.post("/api/calls/{call_id}/close")
def close_call(call_id: str, body: CloseCall):
    call = get_call(call_id)
    if not call: raise HTTPException(404, "Call not found")
    call.update(outcome=body.outcome, notes=body.notes, ended_at=utc_now())
    persist(call)
    return call

@app.post("/api/coach")
async def coach(body: dict[str, str]):
    """Optional Gemini assist. Core call flow never depends on the model."""
    key = os.getenv("GEMINI_API_KEY")
    if not key: return {"available":False, "message":"Add GEMINI_API_KEY to enable the call coach."}
    prompt = f"You are a concise, ethical cold-call coach. Given stage, prospect words, and context, suggest one short follow-up question. Never pressure or invent claims.\nStage: {body.get('stage','')}\nProspect: {body.get('prospect_words','')}\nContext: {body.get('context','')}"
    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={key}", json={"contents":[{"parts":[{"text":prompt}]}]})
    if response.is_error: raise HTTPException(502, "Coach provider is temporarily unavailable")
    data = response.json()
    return {"available":True, "suggestion":data["candidates"][0]["content"]["parts"][0]["text"]}
