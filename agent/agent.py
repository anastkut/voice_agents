import asyncio
import os
from typing import Literal
from uuid import uuid4

import httpx
from dotenv import find_dotenv, load_dotenv
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli, function_tool
from livekit.plugins import openai, silero
from openai import AsyncOpenAI

load_dotenv(find_dotenv())

backend = httpx.AsyncClient(base_url=os.environ["BACKEND_URL"], timeout=10)
oai = AsyncOpenAI(base_url=os.environ["LLM_BASE_URL"], api_key=os.environ["LLM_API_KEY"])

GREETING = ("Thanks for calling EffiGov city services. "
            "Are you reporting a new issue, or checking on an existing request?")

PROMPT = """\
You are the phone agent for EffiGov city services. You talk to residents by voice.
The entire call is in English; always reply in English even if a transcription line looks like another language.
Speak plainly and briefly: one or two short sentences, one question at a time, no lists, no markdown, say digits one at a time. No filler and no repeated recaps. Ask only when information is missing, unclear, or contradictory — but then always ask.
Three things you can do:
1) New issue: collect what the problem is, the exact location (street address, plus apartment or unit number when relevant), and a short description; include the location in the description. Classify the problem into the closest create_case issue type yourself; use other if none fits — do not read the category list to the caller. Judge urgency yourself: urgent for safety hazards or active damage, low for cosmetic issues. Then have them choose a verification question and answer only they would know (for example a childhood nickname) — no personal contact details are collected or stored. Repeat the location and their verification answer back once to confirm, call create_case, tell them their case number and to keep it for follow-ups, and mention once that staff typically review new cases within two business days.
2) Existing request: ask for the case number and call lookup_case, then ask the caller its verification question. Only if their answer clearly matches the expected one, share the status and offer add_note. Otherwise say you cannot share details on that case — do not reveal anything the tool returned, do not add notes, and do not change it. Never share case details without a matching verification answer.
3) Cancel a request: verify the caller exactly like an existing request (no verification needed for a case from this same call), then call cancel_case and confirm it is cancelled.
If a verified caller says an existing problem got worse or better, adjust it with set_urgency.
Ask for each piece of information at most once per call: once the caller gives details or passes verification, retain that for the rest of the call. Never re-ask, and never re-verify a case created or already verified in this same call.
If the caller shares concrete, actionable extras (landmarks, access instructions, best times), save them with add_note; do not note general questions or chatter.
If the caller asks for a human or you cannot help, make sure a case exists (create one if needed), add a note that they requested human follow-up, and say a staff member will call them back.
Do not promise repair dates; if asked, say updates will appear on their case and staff review new cases within about two business days.
Never invent case numbers or statuses; only report what tools return. If a tool fails, apologize and suggest calling back later.
When the caller is done, thank them and say goodbye."""

IssueType = Literal["missed_pickup", "pothole", "streetlight", "water_leak", "noise_complaint",
                    "graffiti", "fallen_tree", "illegal_dumping", "sidewalk_damage", "other"]


class IntakeAgent(Agent):
    def __init__(self, call_id: str):
        super().__init__(instructions=PROMPT)
        self.call_id = call_id
        self.case_id: int | None = None

    async def _link_case(self, case_id: int):
        self.case_id = case_id
        await backend.patch(f"/calls/{self.call_id}", json={"case_id": case_id})

    @function_tool
    async def create_case(self, issue_type: IssueType, description: str,
                          secret_question: str, secret_answer: str,
                          urgency: Literal["low", "normal", "urgent"] = "normal") -> str:
        """File a new service request case.

        Args:
            issue_type: Category of the reported issue.
            description: Short description of the issue, including its location.
            secret_question: Verification question the caller chose for future calls.
            secret_answer: The caller's answer to that question.
            urgency: urgent for safety hazards or active damage, low for cosmetic issues.
        """
        r = await backend.post("/cases", json={
            "issue_type": issue_type, "description": description,
            "secret_question": secret_question, "secret_answer": secret_answer,
            "urgency": urgency, "actor": "caller",
        })
        r.raise_for_status()
        case_id = r.json()["id"]
        await self._link_case(case_id)
        return f"Created case number {case_id}."

    @function_tool
    async def lookup_case(self, case_id: int) -> str:
        """Look up an existing case by case number. Ask the caller the returned
        verification question before sharing anything from the result.

        Args:
            case_id: Case number.
        """
        r = await backend.get(f"/cases/{case_id}")
        if r.status_code != 200:
            return "No case found."
        case = r.json()
        await self._link_case(case["id"])
        return (f"Case {case['id']}: {case['issue_type']}, status {case['status']}, "
                f"about: {case['description']}. Verification question: {case['secret_question']} "
                f"Expected answer: {case['secret_answer']}. Notes: {case['notes'] or 'none'}.")

    @function_tool
    async def set_urgency(self, case_id: int, urgency: Literal["low", "normal", "urgent"]) -> str:
        """Change how urgent an existing case is.

        Args:
            case_id: Case number.
            urgency: New urgency level.
        """
        r = await backend.patch(f"/cases/{case_id}", json={"urgency": urgency, "actor": "caller"})
        if r.status_code == 404:
            return "No case found."
        r.raise_for_status()
        return f"Case {case_id} urgency is now {urgency}."

    @function_tool
    async def cancel_case(self, case_id: int) -> str:
        """Cancel a service request at the caller's ask.

        Args:
            case_id: Case number to cancel.
        """
        r = await backend.patch(f"/cases/{case_id}",
                                json={"status": "cancelled", "actor": "caller"})
        if r.status_code == 404:
            return "No case found."
        r.raise_for_status()
        return f"Case {case_id} is cancelled."

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
                       api_key=os.environ["STT_API_KEY"], language="en"),
        llm=openai.LLM(model=os.environ["LLM_MODEL"], base_url=os.environ["LLM_BASE_URL"],
                       api_key=os.environ["LLM_API_KEY"], temperature=0.3),
        tts=openai.TTS(model=os.environ["TTS_MODEL"], voice=os.environ["TTS_VOICE"],
                       base_url=os.environ["TTS_BASE_URL"], api_key=os.environ["TTS_API_KEY"]),
    )

    agent_obj = IntakeAgent(call_id)

    @session.on("conversation_item_added")
    def on_item(ev):
        item = ev.item
        if getattr(item, "role", None) in ("user", "assistant") and item.text_content:
            asyncio.create_task(backend.post(f"/calls/{call_id}/messages",
                                             json={"role": item.role, "text": item.text_content}))

    async def mark_ended():
        lines = []
        for m in session.history.items:
            if getattr(m, "role", None) in ("user", "assistant") and m.text_content:
                lines.append(f"{m.role}: {m.text_content}")
            elif getattr(m, "output", None):
                lines.append(f"tool: {m.output}")
        transcript = "\n".join(lines)
        summary = None
        if sum(l.startswith("user:") for l in lines) < 2:  # nothing worth summarizing
            await backend.patch(f"/calls/{call_id}", json={"ended": True})
            return
        try:
            resp = await oai.chat.completions.create(
                model=os.environ["LLM_MODEL"],
                messages=[{"role": "user", "content":
                           "Summarize this city-services call in two sentences for staff:"
                           " issue, caller, outcome.\n\n" + transcript}])
            summary = resp.choices[0].message.content
            if agent_obj.case_id:
                review = await oai.chat.completions.create(
                    model=os.environ["LLM_MODEL"],
                    messages=[{"role": "user", "content":
                               "You are a supervisor reviewing a city-services call. The assistant's"
                               " standing instructions were:\n" + PROMPT + "\n\nCompare what the assistant"
                               " told the caller against the tool lines and those instructions. Reply NONE"
                               " if everything is supported; otherwise state in one or two sentences what"
                               " the assistant said about cases, statuses, or timelines that neither the"
                               " tools nor its instructions support.\n\n" + transcript}])
                verdict = (review.choices[0].message.content or "").strip()
                if verdict and not verdict.upper().startswith("NONE"):
                    await backend.post(f"/cases/{agent_obj.case_id}/notes",
                                       json={"text": f"Supervisor flag: {verdict}", "author": "supervisor"})
        except Exception:
            pass  # the call must still be marked ended
        await backend.patch(f"/calls/{call_id}", json={"ended": True, "summary": summary})

    ctx.add_shutdown_callback(mark_ended)

    await session.start(agent=agent_obj, room=ctx.room)
    await ctx.connect()
    session.say(GREETING)


if __name__ == "__main__":
    cli.run_app(server)
