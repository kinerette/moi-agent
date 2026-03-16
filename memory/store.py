"""Local memory store — SQLite + numpy cosine similarity. Zero cost, works offline."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from datetime import datetime

from core.log import log
from llm import gemini

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "memory.db"
_db: sqlite3.Connection | None = None


def _get_db() -> sqlite3.Connection:
    global _db
    if _db is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _db = sqlite3.connect(str(_DB_PATH))
        _db.row_factory = sqlite3.Row
        _db.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                embedding TEXT DEFAULT '[]',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        _db.execute("""
            CREATE TABLE IF NOT EXISTS task_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                instruction TEXT NOT NULL,
                status TEXT NOT NULL,
                result TEXT DEFAULT '',
                source TEXT DEFAULT 'dashboard',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        _db.commit()
        log.info(f"Memory DB initialized: {_DB_PATH}")
    return _db


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Cosine similarity without numpy dependency."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def add(content: str, metadata: dict | None = None) -> int | None:
    """Store a memory with its embedding."""
    try:
        embedding = await gemini.embed(content)
        db = _get_db()
        cursor = db.execute(
            "INSERT INTO memories (content, metadata, embedding) VALUES (?, ?, ?)",
            (content, json.dumps(metadata or {}), json.dumps(embedding)),
        )
        db.commit()
        log.debug(f"Memory stored: {content[:50]}...")
        return cursor.lastrowid
    except Exception as e:
        log.error(f"Memory add error: {e}")
        return None


async def search(query: str, limit: int = 5, threshold: float = 0.5) -> list[dict]:
    """Semantic search in memories using cosine similarity."""
    try:
        query_embedding = await gemini.embed(query)
        if not query_embedding:
            return []

        db = _get_db()
        rows = db.execute("SELECT id, content, metadata, embedding FROM memories").fetchall()

        scored = []
        for row in rows:
            emb = json.loads(row["embedding"])
            sim = _cosine_sim(query_embedding, emb)
            if sim >= threshold:
                scored.append({
                    "id": row["id"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]),
                    "similarity": round(sim, 4),
                })

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:limit]
    except Exception as e:
        log.error(f"Memory search error: {e}")
        return []


async def get_recent(limit: int = 10) -> list[dict]:
    """Get most recent memories."""
    try:
        db = _get_db()
        rows = db.execute(
            "SELECT id, content, metadata, created_at FROM memories ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"Memory get_recent error: {e}")
        return []


async def save_task_history(task_id: str, instruction: str, status: str, result: str, source: str):
    """Save completed task to history."""
    try:
        db = _get_db()
        db.execute(
            "INSERT INTO task_history (task_id, instruction, status, result, source) VALUES (?, ?, ?, ?, ?)",
            (task_id, instruction, status, result[:2000], source),
        )
        db.commit()
    except Exception as e:
        log.error(f"Task history save error: {e}")


def get_stats() -> dict:
    """Get memory stats for dashboard."""
    try:
        db = _get_db()
        mem_count = db.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        task_count = db.execute("SELECT COUNT(*) FROM task_history").fetchone()[0]
        return {"memories": mem_count, "tasks_completed": task_count}
    except Exception:
        return {"memories": 0, "tasks_completed": 0}
