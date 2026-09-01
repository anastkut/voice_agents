# EffiGov Voice Intake Demo

A resident calls an AI voice agent; the agent files, looks up, annotates, escalates,
or cancels service-request cases through the backend; staff triage them on a live
dashboard (streaming transcripts, post-call summaries, full audit history).

- `backend/` — FastAPI + SQLite, the single source of truth. Every write broadcasts
  a websocket ping; the dashboard refetches on ping (2s polling as fallback).
- `agent/` — LiveKit voice agent (OpenAI LLM/STT/TTS via env-configurable,
  OpenAI-compatible endpoints). A stateless HTTP client of the backend with five
  tools; on hang-up it writes a call summary and a supervisor review.
- `web/` — Next.js dashboard: case list with filters, case detail with transcripts
  and history, resident call page at /call.

## Run

Prereqs: uv, Node 20+, livekit-server (`brew install livekit`), an OpenAI API key.

```
cp .env.example .env    # put your OpenAI key in the three *_API_KEY values

# terminal 1
livekit-server --dev
# terminal 2
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000
# terminal 3
cd agent && uv sync && uv run agent.py download-files && uv run agent.py dev
# terminal 4
cd web && npm i && npm run dev
```

Open http://localhost:3000 (staff dashboard) and http://localhost:3000/call
(resident call). Terminal-only voice session without the browser or LiveKit
server: `uv run agent.py console`. Reset all data: `rm backend/effigov.db`
and restart the backend.
