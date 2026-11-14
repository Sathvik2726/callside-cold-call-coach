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
    {"id":"opening", "name":"Opening", "purpose":"Reach the right person, say who you are, and earn a brief moment.", "prompt":"Hi {{first_name}}, I’m [name] from Meridian Growth Partners in Hyderabad. Is now a bad time for a quick minute?", "signals":["Who is this?", "I’m in a meeting / driving", "That person left; this is the wrong number"], "outcomes":["Reached the right person", "Reception / assistant answered", "Unavailable; callback requested", "Wrong person or number"], "tip":"Confirm who answered before explaining. Many calls are short; match their pace."},
    {"id":"purpose", "name":"Purpose", "purpose":"Explain why this specific company and why you called in a sentence they can repeat.", "prompt":"We study growth constraints in Indian businesses and prepare a short, independent growth report. I’m calling because [specific reason this company fits].", "signals":["What does Meridian do?", "Why did you call me / where did you get my number?", "Is this a sales call?"], "outcomes":["Asked what Meridian does", "Asked why them / where number came from", "Thought it was another kind of call", "Understood; let me continue"], "tip":"Say the purpose plainly. Be transparent about the research, possible commercial follow-up, and what is free."},
    {"id":"permission", "name":"Permission", "purpose":"Check whether they are willing to talk now. Yes, no, or a callback time are all useful outcomes.", "prompt":"Would you be open to two minutes now, or is there a better time for me to call?", "signals":["Go ahead, but keep it short", "Call after 2 / tomorrow", "Not now", "They keep talking without answering"], "outcomes":["Clear yes", "Callback time agreed", "Not now; no time set", "Clear no"], "tip":"A vague response is not a yes. If they decline, accept it or agree on a specific callback."},
    {"id":"business", "name":"Their business", "purpose":"Ask about their company and work before talking about Meridian’s offer.", "prompt":"Before I explain our side, could you tell me what your team is focused on at [company]?", "signals":["They answer briefly and wait for the pitch", "They correct your view of the company", "They ask what Meridian does", "They’re not the decision-maker"], "outcomes":["Described their work", "Asked about Meridian first", "Corrected our company / role context", "Not the right person"], "tip":"Let them describe their own business. Don’t assume their role, company status, or authority."},
    {"id":"need", "name":"Their need, in their words", "purpose":"Hear what they are trying to do or struggling with. Capture their words as said.", "prompt":"What are you trying to change or grow right now? What, if anything, is getting in the way?", "signals":["Names a growth goal", "Describes a constraint or challenge", "Says things are fine / no need", "Asks what you can do for a company like theirs"], "outcomes":["Named a goal", "Named a challenge", "No need / things are fine", "Asked what Meridian can do"], "tip":"Listen for their exact phrase. Don’t turn your interpretation into a quote.", "capture_words":True},
    {"id":"objection", "name":"Objection", "purpose":"Understand the reason for hesitation. A reason you hear is more useful than one you argue over.", "prompt":"That makes sense. What is the main concern from your side?", "signals":["We already have a consultant / in-house team", "You have the wrong person", "Send details first", "No interest / stop calling"], "outcomes":["Already has a team / advisor", "Wrong person / decision elsewhere", "Asked for information first", "Clear no / do not call"], "tip":"Acknowledge, clarify once, then respect their answer. Don’t push past a clear no."},
    {"id":"next_step", "name":"Next step", "purpose":"Agree one concrete action, with a time or channel, or leave it there.", "prompt":"Would you prefer the report by email or WhatsApp? If useful, when should I follow up?", "signals":["Send the report by WhatsApp", "Email me the profile", "Call me at a named time", "Speak to a colleague"], "outcomes":["Report by WhatsApp", "Report by email", "Callback / meeting time agreed", "Referred to someone else"], "tip":"Confirm one action, the channel, and the time. A polite yes to a document is not automatically buying intent."},
    {"id":"close", "name":"Close", "purpose":"End clearly and record the true outcome and next action for the next call.", "prompt":"Thanks for your time. I’ll [confirmed action] [when]. Have a good day.", "signals":["Warm goodbye after a no", "Next action repeated back", "Line drops / call ends suddenly", "Outcome is unclear"], "outcomes":["Next action confirmed", "Polite close after a no", "Call dropped / interrupted", "Outcome unclear"], "tip":"Log what actually happened. Don’t turn a polite exchange into interest."},
]

class StartCall(BaseModel):
    prospect: str = "New prospect"
    company: str = ""

class StageResult(BaseModel):
    stage_id: str
    outcome: str = "completed"
    prospect_words: str = ""

class CloseCall(BaseModel):
    outcome: str = "not_logged"
    next_step: str = ""
    next_step_details: str = ""

calls: dict[str, dict[str, Any]] = {}

def persist(call: dict[str, Any]):
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        from supabase import create_client
        client = create_client(url, key)
        client.table("calls").upsert({k: v for k, v in call.items() if k != "stage_results"}).execute()
        for result in call.get("stage_results", []):
            stage = next((s for s in STAGES if s["id"] == result["stage_id"]), None)
            client.table("call_stage_results").upsert({
                "call_id": call["id"], "stage_id": result["stage_id"],
                "stage_name": stage["name"] if stage else result["stage_id"], **result,
            }, on_conflict="call_id,stage_id").execute()

def get_call(call_id: str):
    if call_id in calls:
        return calls[call_id]
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        from supabase import create_client
        client = create_client(url, key)
        rows = client.table("calls").select("*").eq("id", call_id).limit(1).execute().data
        if rows:
            rows[0]["stage_results"] = client.table("call_stage_results").select("stage_id,outcome,prospect_words,saved_at").eq("call_id", call_id).order("saved_at").execute().data
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
    call = {"id":call_id, "prospect":body.prospect, "company":body.company, "current_stage":"opening", "stage_results":[], "outcome":None, "next_step":"", "next_step_details":"", "notes":"", "started_at":utc_now(), "ended_at":None}
    calls[call_id] = call
    persist(call)
    return call

@app.get("/api/calls")
def list_calls():
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        try:
            from supabase import create_client
            client = create_client(url, key)
            rows = client.table("calls").select("*").order("started_at", desc=True).limit(100).execute().data
            ids = [row["id"] for row in rows]
            results = client.table("call_stage_results").select("call_id,stage_id,outcome,prospect_words,saved_at").in_("call_id", ids).order("saved_at").execute().data if ids else []
            by_call: dict[str, list[dict[str, Any]]] = {}
            for result in results:
                result_call_id = result.pop("call_id")
                by_call.setdefault(result_call_id, []).append(result)
            for row in rows:
                row["stage_results"] = by_call.get(row["id"], [])
            return rows
        except Exception:
            pass
    return sorted(calls.values(), key=lambda c: c["started_at"], reverse=True)

@app.post("/api/calls/{call_id}/stage")
def save_stage(call_id: str, body: StageResult):
    call = get_call(call_id)
    if not call: raise HTTPException(404, "Call not found")
    stage = next((s for s in STAGES if s["id"] == body.stage_id), None)
    if not stage: raise HTTPException(422, "Unknown stage")
    if body.outcome not in stage["outcomes"]: raise HTTPException(422, "Outcome does not belong to this stage")
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
    if body.outcome not in {"agreed_to_receive_report", "next_step_agreed", "interested", "follow_up", "call_again", "not_interested", "do_not_call", "wrong_person", "moved_company", "not_logged"}:
        raise HTTPException(422, "Unknown call outcome")
    call.update(outcome=body.outcome, next_step=body.next_step, next_step_details=body.next_step_details,
                notes=next((r.get("prospect_words", "") for r in call["stage_results"] if r["stage_id"] == "need"), ""), ended_at=utc_now())
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
