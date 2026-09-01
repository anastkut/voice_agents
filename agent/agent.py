import os
from typing import Literal

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
Speak plainly: one or two short sentences, one question at a time, no lists, no markdown, say digits one at a time.
Two things you can do:
1) New issue: collect full name, phone number, issue type (missed trash pickup, pothole, streetlight, water leak, or other), and a short description, then call create_case and tell them their case number.
2) Existing request: ask for their phone number or case number, call lookup_case, and tell them the status. Offer to add a note to the case with add_note.
Never invent case numbers or statuses; only report what tools return. If a tool fails, apologize and suggest calling back later.
When the caller is done, thank them and say goodbye."""

IssueType = Literal["missed_pickup", "pothole", "streetlight", "water_leak", "other"]


class IntakeAgent(Agent):
    def __init__(self):
        super().__init__(instructions=PROMPT)

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
        return f"Created case number {r.json()['id']}."

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
        return f"Case {case['id']}: {case['issue_type']}, status {case['status']}. Notes: {case['notes'] or 'none'}."

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
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=openai.STT(model=os.environ["STT_MODEL"], base_url=os.environ["STT_BASE_URL"],
                       api_key=os.environ["STT_API_KEY"]),
        llm=openai.LLM(model=os.environ["LLM_MODEL"], base_url=os.environ["LLM_BASE_URL"],
                       api_key=os.environ["LLM_API_KEY"], temperature=0.3),
        tts=openai.TTS(model=os.environ["TTS_MODEL"], voice=os.environ["TTS_VOICE"],
                       base_url=os.environ["TTS_BASE_URL"], api_key=os.environ["TTS_API_KEY"]),
    )
    await session.start(agent=IntakeAgent(), room=ctx.room)
    await ctx.connect()
    session.say(GREETING)


if __name__ == "__main__":
    cli.run_app(server)
