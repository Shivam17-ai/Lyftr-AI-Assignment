import asyncio
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Dict, List, Optional
from app.config import settings


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or settings.sqlite_db_path
    conn = sqlite3.connect(path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def _init_db_sync(db_path: Optional[str] = None) -> None:
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL
            );
            """)
            conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                system_prompt TEXT,
                created_at TEXT NOT NULL
            );
            """)
    finally:
        conn.close()


async def init_db(db_path: Optional[str] = None) -> None:
    await asyncio.to_thread(_init_db_sync, db_path)


def _check_db_healthy_sync(db_path: Optional[str] = None) -> bool:
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        return cursor.fetchone()[0] == 1
    finally:
        conn.close()


async def check_db_healthy(db_path: Optional[str] = None) -> bool:
    return await asyncio.to_thread(_check_db_healthy_sync, db_path)


def _get_session_system_prompt_sync(session_id: str, db_path: Optional[str] = None) -> Optional[str]:
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT system_prompt FROM sessions WHERE session_id = ?;", (session_id,))
        row = cursor.fetchone()
        if row and row["system_prompt"] is not None:
            return row["system_prompt"]
        return None
    finally:
        conn.close()


async def get_session_system_prompt(session_id: str, db_path: Optional[str] = None) -> Optional[str]:
    return await asyncio.to_thread(_get_session_system_prompt_sync, session_id, db_path)


def _upsert_session_system_prompt_sync(session_id: str, system_prompt: str, db_path: Optional[str] = None) -> None:
    conn = get_connection(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            conn.execute("""
            INSERT INTO sessions (session_id, system_prompt, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET system_prompt = excluded.system_prompt;
            """, (session_id, system_prompt, now_iso))
    finally:
        conn.close()


async def upsert_session_system_prompt(session_id: str, system_prompt: str, db_path: Optional[str] = None) -> None:
    await asyncio.to_thread(_upsert_session_system_prompt_sync, session_id, system_prompt, db_path)


def _get_session_messages_sync(session_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT role, content, metadata
        FROM messages
        WHERE session_id = ?
        ORDER BY id ASC;
        """, (session_id,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            meta = None
            if r["role"] == "assistant" and r["metadata"]:
                try:
                    meta = json.loads(r["metadata"])
                except Exception:
                    meta = {}
            item = {
                "role": r["role"],
                "content": r["content"],
            }
            if meta is not None:
                item["metadata"] = meta
            result.append(item)
        return result
    finally:
        conn.close()


async def get_session_messages(session_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    return await asyncio.to_thread(_get_session_messages_sync, session_id, db_path)


def _list_sessions_sync(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT s.session_id,
               (SELECT content FROM messages WHERE messages.session_id = s.session_id AND role = 'user' ORDER BY id ASC LIMIT 1) as title,
               MAX(created_at) as last_active
        FROM (SELECT DISTINCT session_id FROM messages) s
        GROUP BY s.session_id
        ORDER BY last_active DESC;
        """)
        rows = cursor.fetchall()
        return [
            {
                "session_id": r["session_id"],
                "title": (r["title"][:40] + "...") if r["title"] and len(r["title"]) > 40 else (r["title"] or r["session_id"]),
                "last_active": r["last_active"]
            }
            for r in rows
        ]
    finally:
        conn.close()


async def list_sessions(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    return await asyncio.to_thread(_list_sessions_sync, db_path)


def _save_turn_transaction_sync(
    session_id: str,
    user_message: str,
    assistant_reply: str,
    assistant_metadata: Dict[str, Any],
    db_path: Optional[str] = None
) -> None:
    conn = get_connection(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    meta_json = json.dumps(assistant_metadata)
    try:
        with conn:
            conn.execute("""
            INSERT INTO messages (session_id, role, content, metadata, created_at)
            VALUES (?, 'user', ?, NULL, ?);
            """, (session_id, user_message, now_iso))
            conn.execute("""
            INSERT INTO messages (session_id, role, content, metadata, created_at)
            VALUES (?, 'assistant', ?, ?, ?);
            """, (session_id, assistant_reply, meta_json, now_iso))
    finally:
        conn.close()


async def save_turn_transaction(
    session_id: str,
    user_message: str,
    assistant_reply: str,
    assistant_metadata: Dict[str, Any],
    db_path: Optional[str] = None
) -> None:
    await asyncio.to_thread(
        _save_turn_transaction_sync,
        session_id,
        user_message,
        assistant_reply,
        assistant_metadata,
        db_path
    )
