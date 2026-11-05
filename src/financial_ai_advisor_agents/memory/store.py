import json
import sqlite3
from pathlib import Path
from typing import Any

from financial_ai_advisor_agents.schemas.memory import MemoryContext, Message


class MemoryStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)

    def context(self, user_id: str, limit: int = 6) -> MemoryContext:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT role, content FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
            profile_row = connection.execute("SELECT data FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
        history = [Message(role=row[0], content=row[1]) for row in reversed(rows)]
        profile = json.loads(profile_row[0]) if profile_row else {}
        return MemoryContext(user_id=user_id, profile=profile, history=history)

    def append_message(self, user_id: str, role: str, content: str) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError("Message role must be user or assistant")
        with self._connect() as connection:
            connection.execute("INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))

    def update_profile(self, user_id: str, fields: dict[str, Any]) -> None:
        current = self.context(user_id).profile
        current.update(fields)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO profiles (user_id, data, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(user_id) DO UPDATE SET data = excluded.data, updated_at = CURRENT_TIMESTAMP",
                (user_id, json.dumps(current, ensure_ascii=False)),
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)
