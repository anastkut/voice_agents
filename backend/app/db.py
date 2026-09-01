import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

conn = sqlite3.connect(Path(__file__).parent.parent / "effigov.db", check_same_thread=False)
conn.row_factory = sqlite3.Row
conn.execute("""
    CREATE TABLE IF NOT EXISTS cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT, updated_at TEXT, status TEXT,
        name TEXT, phone TEXT, issue_type TEXT, description TEXT,
        notes TEXT DEFAULT ''
    )
""")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def normalize_phone(s: str) -> str:
    return re.sub(r"\D", "", s)


def create_case(name: str, phone: str, issue_type: str, description: str) -> dict:
    ts = now()
    with conn:
        cur = conn.execute(
            "INSERT INTO cases (created_at, updated_at, status, name, phone, issue_type, description)"
            " VALUES (?, ?, 'new', ?, ?, ?, ?)",
            (ts, ts, name, normalize_phone(phone), issue_type, description),
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


def update_case(case_id: int, fields: dict) -> dict | None:
    if not get_case(case_id):
        return None
    fields["updated_at"] = now()
    cols = ", ".join(f"{k} = ?" for k in fields)
    with conn:
        conn.execute(f"UPDATE cases SET {cols} WHERE id = ?", (*fields.values(), case_id))
    return get_case(case_id)


def add_note(case_id: int, text: str, author: str) -> dict | None:
    case = get_case(case_id)
    if not case:
        return None
    stamp = datetime.now(timezone.utc).strftime("%H:%M")
    return update_case(case_id, {"notes": case["notes"] + f"[{stamp} {author}] {text}\n"})
