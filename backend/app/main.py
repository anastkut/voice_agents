import os
from secrets import token_hex
from typing import Literal

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, HTTPException
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

IssueType = Literal["missed_pickup", "pothole", "streetlight", "water_leak", "other"]


class CaseIn(BaseModel):
    name: str
    phone: str
    issue_type: IssueType
    description: str


class CasePatch(BaseModel):
    status: Literal["new", "in_progress", "resolved"] | None = None
    notes: str | None = None
    issue_type: IssueType | None = None
    description: str | None = None


class NoteIn(BaseModel):
    text: str
    author: str


def case_or_404(case: dict | None) -> dict:
    if case is None:
        raise HTTPException(404, "case not found")
    return case


@app.post("/cases")
async def create_case(body: CaseIn):
    return db.create_case(body.name, body.phone, body.issue_type, body.description)


@app.get("/cases")
async def list_cases(phone: str | None = None):
    return db.list_cases(phone)


@app.get("/cases/{case_id}")
async def get_case(case_id: int):
    return case_or_404(db.get_case(case_id))


@app.patch("/cases/{case_id}")
async def patch_case(case_id: int, body: CasePatch):
    return case_or_404(db.update_case(case_id, body.model_dump(exclude_none=True)))


@app.post("/cases/{case_id}/notes")
async def add_note(case_id: int, body: NoteIn):
    return case_or_404(db.add_note(case_id, body.text, body.author))


@app.get("/livekit/token")
async def livekit_token():
    token = (
        api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity("resident-" + token_hex(4))
        .with_grants(api.VideoGrants(room_join=True, room="call-" + token_hex(4)))
        .to_jwt()
    )
    return {"url": LIVEKIT_URL, "token": token}
