# EffiGov Voice Intake Demo

A resident calls an AI voice agent, the agent files or looks up service-request
cases through the backend, and staff triage them on the dashboard.

- `backend/` — FastAPI + SQLite, owns all case data
- `agent/` — LiveKit voice agent (OpenAI LLM/STT/TTS), an HTTP client of the backend
- `web/` — Next.js dashboard: case list, case detail, resident call page

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
(resident call). For a terminal-only voice session without the browser or
LiveKit server: `uv run agent.py console`.
