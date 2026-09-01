import asyncio
import os
from typing import Literal
from uuid import uuid4

import httpx
from dotenv import find_dotenv, load_dotenv
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli, function_tool
from livekit.plugins import openai, silero

load_dotenv(find_dotenv())

backend = httpx.AsyncClient(base_url=os.environ["BACKEND_URL"], timeout=10)

GREETING = ("Thanks for calling EffiGov city services. "
            "Are you reporting a new issue, or checking on an existing request?")

PROMPT = """\
You are the phone agent for EffiGov city services. You talk to residents by voice.
The entire call is in English; always reply in English even if a transcription line looks like another language.
Speak plainly: one or two short sentences, one question at a time, no lists, no markdown, say digits one at a time.
Two things you can do:
1) New issue: collect full name, phone number, issue type (missed trash pickup, pothole, streetlight, water leak, or other), and a short description, then call create_case and tell them their case number.
2) Existing request: ask for their phone number or case number, their full name, and a brief description of what the case is about. Call lookup_case and compare its result with what they told you: only if the name and description clearly match, share the status and offer to add a note with add_note. If they do not match, say you cannot share details on that case — do not reveal anything the tool returned and do not add notes. Never share case details based on a case number alone.
If the caller asks about a case created or verified earlier in this same call, answer from what you already know; do not re-collect their details or re-verify them.
Never invent case numbers or statuses; only report what tools return. If a tool fails, apologize and suggest calling back later.
When the caller is done, thank them and say goodbye."""

IssueType = Literal["missed_pickup", "pothole", "streetlight", "water_leak", "other"]


class IntakeAgent(Agent):
    def __init__(self, call_id: str):
        super().__init__(instructions=PROMPT)
        self.call_id = call_id

    async def _link_case(self, case_id: int):
        await backend.patch(f"/calls/{self.call_id}", json={"case_id": case_id})

    @function_tool
    async def create_case(self, name: str, phone: str, issue_type: IssueType, description: str) -> str:
        """File a new service request case.

        Args:
            name: Caller's full name.
            phone: Caller's phone number.
            issue_type: Category of the reported issue.
            description: Short description of the issue.
        """
        r = await backend.post("/cases", json={
            "name": name, "phone": phone, "issue_type": issue_type, "description": description,
        })
        r.raise_for_status()
        case_id = r.json()["id"]
        await self._link_case(case_id)
        return f"Created case number {case_id}."

    @function_tool
    async def lookup_case(self, phone: str = "", case_id: int = 0) -> str:
        """Look up an existing case by phone number or case number.

        Args:
            phone: Caller's phone number, if they gave one.
            case_id: Case number, if they gave one.
        """
        if case_id:
            r = await backend.get(f"/cases/{case_id}")
            case = r.json() if r.status_code == 200 else None
        else:
            cases = (await backend.get("/cases", params={"phone": phone})).json()
            case = cases[0] if cases else None
        if not case:
            return "No case found."
        await self._link_case(case["id"])
        return (f"Case {case['id']}, filed by {case['name']}, about: {case['description']}. "
                f"Issue type {case['issue_type']}, status {case['status']}. Notes: {case['notes'] or 'none'}.")

    @function_tool
    async def add_note(self, case_id: int, note: str) -> str:
        """Add a note from the caller to an existing case.

        Args:
            case_id: Case number to attach the note to.
            note: The note text.
        """
        r = await backend.post(f"/cases/{case_id}/notes", json={"text": note, "author": "caller"})
        r.raise_for_status()
        return f"Note added to case {case_id}."


server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    call_id = uuid4().hex[:8]
    await backend.post("/calls", json={"id": call_id})

    session = AgentSession(
        # explicit local VAD turn detection; the default tries LiveKit Cloud's paid gateway
        turn_detection="vad",
        vad=silero.VAD.load(),
        stt=openai.STT(model=os.environ["STT_MODEL"], base_url=os.environ["STT_BASE_URL"],
                       api_key=os.environ["STT_API_KEY"], language="en",
                       prompt="An English phone call to city services. Phone numbers are spoken digit by digit."),
        llm=openai.LLM(model=os.environ["LLM_MODEL"], base_url=os.environ["LLM_BASE_URL"],
                       api_key=os.environ["LLM_API_KEY"], temperature=0.3),
        tts=openai.TTS(model=os.environ["TTS_MODEL"], voice=os.environ["TTS_VOICE"],
                       base_url=os.environ["TTS_BASE_URL"], api_key=os.environ["TTS_API_KEY"]),
    )

    @session.on("conversation_item_added")
    def on_item(ev):
        item = ev.item
        if getattr(item, "role", None) in ("user", "assistant") and item.text_content:
            asyncio.create_task(backend.post(f"/calls/{call_id}/messages",
                                             json={"role": item.role, "text": item.text_content}))

    async def mark_ended():
        await backend.patch(f"/calls/{call_id}", json={"ended": True})

    ctx.add_shutdown_callback(mark_ended)

    await session.start(agent=IntakeAgent(call_id), room=ctx.room)
    await ctx.connect()
    session.say(GREETING)


if __name__ == "__main__":
    cli.run_app(server)
