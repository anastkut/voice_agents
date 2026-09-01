# Architecture

Three processes on localhost. The backend is the single writer; everything else is
an HTTP client of it.

```
caller ⇄ web /call ⇄ livekit-server ⇄ agent ──HTTP──▶ backend ⇄ SQLite
                                                         │  ▲
staff  ⇄ web dashboard ◀── ws ping + 2s poll ────────────┘  └── staff edits
```

## Components

**backend/** (FastAPI, `app/db.py` + `app/main.py`)
Owns `backend/effigov.db` (SQLite, schema auto-created at import). REST for cases
and calls, one websocket at `/ws`, and `/livekit/token` which mints room-join JWTs.
Every write endpoint broadcasts `{"type": "case"|"call"|"message"}` to all websocket
clients — an invalidation ping, never a payload. Audit events are written in the
same transaction as the change they record.

**agent/** (`agent.py`, LiveKit Agents)
Registers with livekit-server and auto-joins every new room. Pipeline per turn:
Silero VAD (local) → STT → LLM → TTS, all OpenAI-compatible endpoints configured in
`.env`. The LLM extracts structured data by calling five typed tools — thin HTTP
wrappers: `create_case`, `lookup_case`, `add_note`, `set_urgency`, `cancel_case`.
Enum-typed parameters are the extraction schema. Every conversation line is POSTed
to the backend as it happens. On shutdown: mark the call ended, write a two-sentence
summary, then a supervisor pass — a second LLM request that checks the agent's
statements against tool outputs and its instructions, flagging unsupported claims
as a note on the case.

**web/** (Next.js, all pages client-side)
`/` case list with active-call strip, filters, streaming transcripts. `/cases/[id]`
detail: editable status/urgency/notes (form re-seeds from the server unless the
user is mid-edit), audit history, per-call summary + transcript. `/call` resident
phone stand-in. `useLive()` opens one websocket per page and refetches all SWR keys
on any ping; 2s polling is the fallback. The LiveKit `Room` lives in a provider in
the layout, so a call survives navigation and ends only on hang up.

## Data model

```
cases        id, created_at, updated_at, status, urgency, passphrase,
             issue_type, description, notes
calls        id, case_id → cases, started_at, ended_at, summary
messages     id, call_id → calls, ts, role, text          (transcript history)
case_events  id, case_id → cases, ts, actor, field, old, new   (audit trail)
```

`cases`/`calls` hold current state; `messages`/`case_events` hold history.
Statuses: `new → triaged → scheduled → in_progress → resolved`, plus `cancelled`
as an exit. Records are never deleted.

## Authority

- **Caller** (via agent tools): create a case, look up / note / re-prioritize /
  cancel their own. No personal contact details are stored: at creation the backend
  generates a four-word passphrase (read to the caller once), and follow-up lookups
  go through `/cases/{id}/verify`, which compares server-side and returns the same
  "not found" whether the id or the phrase is wrong — the LLM never sees the stored
  passphrase, and a case's existence is never disclosed without a match.
- **Staff** (dashboard): everything, including the workflow ladder.
- **Supervisor** (post-call LLM pass): annotate only.

## Configuration

One `.env` at the repo root (see `.env.example`). LLM, STT, and TTS each take a
base URL + key + model, so swapping providers (OpenAI ↔ Anthropic ↔ local
open-weights) is config, not code. LiveKit runs locally with `livekit-server
--dev` and its built-in dev keypair; production would swap the three LIVEKIT_*
values for a cloud project and feed telephony (SIP) into the same rooms — the
agent code is unchanged.
