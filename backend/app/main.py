import os
from secrets import token_hex
from typing import Literal

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from livekit import api
from pydantic import BaseModel

from app import db

load_dotenv(find_dotenv())

LIVEKIT_URL = os.environ["LIVEKIT_URL"]
LIVEKIT_API_KEY = os.environ["LIVEKIT_API_KEY"]
LIVEKIT_API_SECRET = os.environ["LIVEKIT_API_SECRET"]

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
                   allow_methods=["*"], allow_headers=["*"])

IssueType = Literal["missed_pickup", "pothole", "streetlight", "water_leak", "noise_complaint",
                    "graffiti", "fallen_tree", "illegal_dumping", "sidewalk_damage", "other"]
Urgency = Literal["low", "normal", "urgent"]


class CaseIn(BaseModel):
    issue_type: IssueType
    description: str
    secret_question: str
    secret_answer: str
    urgency: Urgency = "normal"
    actor: Literal["staff", "caller"] = "staff"


class CasePatch(BaseModel):
    status: Literal["new", "triaged", "scheduled", "in_progress", "resolved", "cancelled"] | None = None
    urgency: Urgency | None = None
    notes: str | None = None
    issue_type: IssueType | None = None
    description: str | None = None
    actor: Literal["staff", "caller"] = "staff"


class NoteIn(BaseModel):
    text: str
    author: str


class CallIn(BaseModel):
    id: str


class CallPatch(BaseModel):
    case_id: int | None = None
    ended: bool | None = None
    summary: str | None = None


class MessageIn(BaseModel):
    role: Literal["user", "assistant"]
    text: str


def case_or_404(case: dict | None) -> dict:
    if case is None:
        raise HTTPException(404, "case not found")
    return case


clients: set[WebSocket] = set()


async def broadcast(msg: dict):
    for ws in list(clients):
        try:
            await ws.send_json(msg)
        except Exception:
            clients.discard(ws)


@app.websocket("/ws")
async def ws_updates(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)


@app.post("/cases")
async def create_case(body: CaseIn):
    case = db.create_case(body.issue_type, body.description, body.secret_question,
                          body.secret_answer, body.urgency, body.actor)
    await broadcast({"type": "case", "case_id": case["id"]})
    return case


@app.get("/cases")
async def list_cases():
    return db.list_cases()


@app.get("/cases/{case_id}")
async def get_case(case_id: int):
    return case_or_404(db.get_case(case_id)) | {
        "calls": db.case_calls(case_id), "events": db.case_events(case_id)}


@app.patch("/cases/{case_id}")
async def patch_case(case_id: int, body: CasePatch):
    fields = body.model_dump(exclude_none=True)
    actor = fields.pop("actor")
    case = case_or_404(db.update_case(case_id, fields, actor))
    await broadcast({"type": "case", "case_id": case_id})
    return case


@app.post("/cases/{case_id}/notes")
async def add_note(case_id: int, body: NoteIn):
    case = case_or_404(db.add_note(case_id, body.text, body.author))
    await broadcast({"type": "case", "case_id": case_id})
    return case


@app.post("/calls")
async def create_call(body: CallIn):
    call = db.create_call(body.id)
    await broadcast({"type": "call", "call_id": call["id"]})
    return call


@app.patch("/calls/{call_id}")
async def patch_call(call_id: str, body: CallPatch):
    fields: dict = {}
    if body.case_id is not None:
        fields["case_id"] = body.case_id
    if body.summary is not None:
        fields["summary"] = body.summary
    if body.ended:
        fields["ended_at"] = db.now()
    call = case_or_404(db.update_call(call_id, fields))
    await broadcast({"type": "call", "call_id": call_id})
    return call


@app.post("/calls/{call_id}/messages")
async def add_message(call_id: str, body: MessageIn):
    message = db.add_message(call_id, body.role, body.text)
    await broadcast({"type": "message", "call_id": call_id})
    return message


@app.get("/calls")
async def list_active_calls():
    return db.active_calls()


@app.get("/livekit/token")
async def livekit_token():
    token = (
        api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity("resident-" + token_hex(4))
        .with_grants(api.VideoGrants(room_join=True, room="call-" + token_hex(4)))
        .to_jwt()
    )
    return {"url": LIVEKIT_URL, "token": token}
