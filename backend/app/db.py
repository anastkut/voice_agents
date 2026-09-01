import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

conn = sqlite3.connect(Path(__file__).parent.parent / "effigov.db", check_same_thread=False)
conn.row_factory = sqlite3.Row
conn.execute("""
    CREATE TABLE IF NOT EXISTS cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT, updated_at TEXT, status TEXT, urgency TEXT DEFAULT 'normal',
        name TEXT, phone TEXT, issue_type TEXT, description TEXT,
        notes TEXT DEFAULT ''
    )
""")
conn.execute("""
    CREATE TABLE IF NOT EXISTS calls (
        id TEXT PRIMARY KEY,
        case_id INTEGER REFERENCES cases(id),
        started_at TEXT, ended_at TEXT, summary TEXT
    )
""")
conn.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        call_id TEXT REFERENCES calls(id),
        ts TEXT, role TEXT, text TEXT
    )
""")
conn.execute("""
    CREATE TABLE IF NOT EXISTS case_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER REFERENCES cases(id),
        ts TEXT, actor TEXT, field TEXT, old TEXT, new TEXT
    )
""")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def normalize_phone(s: str) -> str:
    return re.sub(r"\D", "", s)


def create_case(name: str, phone: str, issue_type: str, description: str, urgency: str) -> dict:
    ts = now()
    with conn:
        cur = conn.execute(
            "INSERT INTO cases (created_at, updated_at, status, urgency, name, phone, issue_type, description)"
            " VALUES (?, ?, 'new', ?, ?, ?, ?, ?)",
            (ts, ts, urgency, name, normalize_phone(phone), issue_type, description),
        )
    return get_case(cur.lastrowid)


def list_cases(phone: str | None = None) -> list[dict]:
    sql, args = "SELECT * FROM cases", ()
    if phone:
        sql, args = sql + " WHERE phone = ?", (normalize_phone(phone),)
    return [dict(r) for r in conn.execute(sql + " ORDER BY id DESC", args)]


def get_case(case_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    return dict(row) if row else None


def update_case(case_id: int, fields: dict, actor: str = "staff") -> dict | None:
    case = get_case(case_id)
    if not case:
        return None
    changes = {k: v for k, v in fields.items() if case[k] != v}
    fields["updated_at"] = now()
    cols = ", ".join(f"{k} = ?" for k in fields)
    with conn:
        conn.execute(f"UPDATE cases SET {cols} WHERE id = ?", (*fields.values(), case_id))
        for k, v in changes.items():
            old, new = str(case[k]), str(v)
            if k == "notes" and new.startswith(old):
                old, new = "", new[len(old):].strip()  # log just the appended note
            conn.execute(
                "INSERT INTO case_events (case_id, ts, actor, field, old, new) VALUES (?, ?, ?, ?, ?, ?)",
                (case_id, now(), actor, k, old, new))
    return get_case(case_id)


def add_note(case_id: int, text: str, author: str) -> dict | None:
    case = get_case(case_id)
    if not case:
        return None
    stamp = datetime.now(timezone.utc).strftime("%H:%M")
    return update_case(case_id, {"notes": case["notes"] + f"[{stamp} {author}] {text}\n"}, actor=author)


def case_events(case_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM case_events WHERE case_id = ? ORDER BY id", (case_id,))]


def create_call(call_id: str) -> dict:
    with conn:
        conn.execute("INSERT INTO calls (id, started_at) VALUES (?, ?)", (call_id, now()))
    return get_call(call_id)


def get_call(call_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
    return dict(row) if row else None


def update_call(call_id: str, fields: dict) -> dict | None:
    if not get_call(call_id):
        return None
    cols = ", ".join(f"{k} = ?" for k in fields)
    with conn:
        conn.execute(f"UPDATE calls SET {cols} WHERE id = ?", (*fields.values(), call_id))
    return get_call(call_id)


def add_message(call_id: str, role: str, text: str) -> dict:
    with conn:
        cur = conn.execute("INSERT INTO messages (call_id, ts, role, text) VALUES (?, ?, ?, ?)",
                           (call_id, now(), role, text))
    return dict(conn.execute("SELECT * FROM messages WHERE id = ?", (cur.lastrowid,)).fetchone())


def call_messages(call_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM messages WHERE call_id = ? ORDER BY id", (call_id,))]


def active_calls() -> list[dict]:
    rows = conn.execute("SELECT * FROM calls WHERE ended_at IS NULL ORDER BY started_at DESC")
    return [dict(r) | {"case": get_case(r["case_id"]) if r["case_id"] else None,
                       "messages": call_messages(r["id"])} for r in rows]


def case_calls(case_id: int) -> list[dict]:
    rows = conn.execute("SELECT * FROM calls WHERE case_id = ? ORDER BY started_at", (case_id,))
    return [dict(r) | {"messages": call_messages(r["id"])} for r in rows]
