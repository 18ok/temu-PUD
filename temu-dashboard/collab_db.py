#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLite collaboration index for the Temu dashboard backend.

This module is intentionally small: OSS remains the object store for uploaded
summary JSON, while SQLite starts as the local collaboration index and audit log.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2


def db_path() -> Path:
    configured = os.environ.get("TEMU_DB_PATH", "").strip()
    if configured:
        return Path(configured)
    return Path(os.getcwd()) / "data" / "temu_collab.sqlite3"


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS upload_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                display_name TEXT NOT NULL,
                group_id TEXT,
                group_name TEXT,
                summary_date TEXT,
                oss_key TEXT NOT NULL UNIQUE,
                align_score INTEGER,
                score_label TEXT,
                spu_count INTEGER DEFAULT 0,
                store_count INTEGER DEFAULT 0,
                uploaded_at TEXT,
                created_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_upload_index_user_time
                ON upload_index(user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_upload_index_group_time
                ON upload_index(group_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS pk_latest (
                user_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                group_id TEXT,
                group_name TEXT,
                summary_date TEXT,
                oss_key TEXT NOT NULL,
                align_score INTEGER,
                score_label TEXT,
                gold_pct REAL,
                avg_margin REAL,
                roas REAL,
                avg_day_sales REAL,
                spu_count INTEGER DEFAULT 0,
                store_count INTEGER DEFAULT 0,
                uploaded_at TEXT,
                updated_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_pk_latest_score
                ON pk_latest(align_score DESC, display_name);
            CREATE INDEX IF NOT EXISTS idx_pk_latest_group_score
                ON pk_latest(group_id, align_score DESC, display_name);

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_id TEXT,
                actor_name TEXT,
                role TEXT,
                action TEXT NOT NULL,
                detail_json TEXT NOT NULL DEFAULT '{}',
                created_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_audit_logs_time
                ON audit_logs(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_audit_logs_actor
                ON audit_logs(actor_id, created_at DESC);
            """
        )
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )


def safe_call(fn, *args, **kwargs) -> bool:
    try:
        init_db()
        fn(*args, **kwargs)
        return True
    except Exception as exc:
        # Database mirroring must not break the existing OSS-first workflow.
        print(f"[DB] mirror skipped: {exc}")
        return False


def record_audit(action: str, user: dict | None = None, detail: dict | None = None) -> None:
    def _write() -> None:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_logs(actor_id, actor_name, role, action, detail_json, created_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    (user or {}).get("id"),
                    (user or {}).get("display_name"),
                    (user or {}).get("role"),
                    action,
                    json.dumps(detail or {}, ensure_ascii=False),
                    int(time.time()),
                ),
            )

    safe_call(_write)


def record_upload(entry: dict[str, Any]) -> None:
    def _write() -> None:
        now = int(time.time())
        with connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO upload_index(
                    user_id, display_name, group_id, group_name, summary_date,
                    oss_key, align_score, score_label, spu_count, store_count,
                    uploaded_at, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.get("user_id", ""),
                    entry.get("display_name", ""),
                    entry.get("group_id"),
                    entry.get("group_name"),
                    entry.get("summary_date"),
                    entry.get("oss_key", ""),
                    entry.get("align_score"),
                    entry.get("score_label"),
                    entry.get("spu_count") or 0,
                    entry.get("store_count") or 0,
                    entry.get("uploaded_at"),
                    now,
                ),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO pk_latest(
                    user_id, display_name, group_id, group_name, summary_date,
                    oss_key, align_score, score_label, gold_pct, avg_margin,
                    roas, avg_day_sales, spu_count, store_count, uploaded_at,
                    updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.get("user_id", ""),
                    entry.get("display_name", ""),
                    entry.get("group_id"),
                    entry.get("group_name"),
                    entry.get("summary_date"),
                    entry.get("oss_key", ""),
                    entry.get("align_score"),
                    entry.get("score_label"),
                    entry.get("gold_pct"),
                    entry.get("avg_margin"),
                    entry.get("roas"),
                    entry.get("avg_day_sales"),
                    entry.get("spu_count") or 0,
                    entry.get("store_count") or 0,
                    entry.get("uploaded_at"),
                    now,
                ),
            )

    safe_call(_write)


def latest_pk_entries(
    *,
    role: str = "admin",
    user_id: str | None = None,
    group_id: str | None = None,
) -> dict[str, Any]:
    init_db()
    params: list[Any] = []
    where = ""
    if role == "operator":
        if not user_id:
            return {"updated_at": None, "entries": []}
        where = "WHERE user_id = ?"
        params.append(user_id)
    elif role == "supervisor":
        clauses = []
        if group_id:
            clauses.append("group_id = ?")
            params.append(group_id)
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        if not clauses:
            return {"updated_at": None, "entries": []}
        where = "WHERE " + " OR ".join(clauses)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT user_id, display_name, group_id, group_name, summary_date,
                   oss_key, align_score, score_label, gold_pct, avg_margin,
                   roas, avg_day_sales, spu_count, store_count, uploaded_at,
                   updated_at
            FROM pk_latest
            {where}
            ORDER BY align_score DESC, display_name
            """,
            params,
        ).fetchall()
    entries = [
        {
            "user_id": row["user_id"],
            "display_name": row["display_name"] or "",
            "group_id": row["group_id"],
            "group_name": row["group_name"] or "",
            "summary_date": row["summary_date"],
            "oss_key": row["oss_key"],
            "align_score": row["align_score"],
            "score_label": row["score_label"] or "",
            "gold_pct": row["gold_pct"],
            "avg_margin": row["avg_margin"],
            "roas": row["roas"],
            "avg_day_sales": row["avg_day_sales"],
            "spu_count": row["spu_count"],
            "store_count": row["store_count"],
            "uploaded_at": row["uploaded_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]
    updated_at = max((row["updated_at"] for row in rows), default=None)
    return {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(updated_at)) if updated_at else None,
        "entries": entries,
    }


def recent_uploads(
    limit: int = 20,
    *,
    role: str = "admin",
    user_id: str | None = None,
    group_id: str | None = None,
) -> list[dict[str, Any]]:
    init_db()
    limit = max(1, min(int(limit or 20), 100))
    params: list[Any] = []
    where = ""
    if role == "operator":
        if not user_id:
            return []
        where = "WHERE user_id = ?"
        params.append(user_id)
    elif role == "supervisor":
        clauses = []
        if group_id:
            clauses.append("group_id = ?")
            params.append(group_id)
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        if not clauses:
            return []
        where = "WHERE " + " OR ".join(clauses)
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT user_id, display_name, group_id, group_name, oss_key,
                   align_score, score_label, spu_count, store_count, uploaded_at,
                   created_at
            FROM upload_index
            {where}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [
        {
            "user_id": row["user_id"],
            "display_name": row["display_name"] or "",
            "group_id": row["group_id"],
            "group_name": row["group_name"] or "",
            "at": row["uploaded_at"],
            "oss_key": row["oss_key"],
            "align_score": row["align_score"],
            "score_label": row["score_label"],
            "spu_count": row["spu_count"],
            "store_count": row["store_count"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def recent_audit(limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    limit = max(1, min(int(limit or 20), 100))
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT actor_id, actor_name, role, action, detail_json, created_at
            FROM audit_logs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    items = []
    for row in rows:
        try:
            detail = json.loads(row["detail_json"] or "{}")
        except json.JSONDecodeError:
            detail = {}
        items.append({
            "actor_id": row["actor_id"],
            "actor_name": row["actor_name"] or "",
            "role": row["role"] or "",
            "action": row["action"],
            "detail": detail,
            "created_at": row["created_at"],
            "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row["created_at"])),
        })
    return items


def status() -> dict[str, Any]:
    init_db()
    path = db_path()
    with connect() as conn:
        tables = [
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        upload_count = conn.execute("SELECT COUNT(*) AS n FROM upload_index").fetchone()["n"]
        pk_count = conn.execute("SELECT COUNT(*) AS n FROM pk_latest").fetchone()["n"]
        audit_count = conn.execute("SELECT COUNT(*) AS n FROM audit_logs").fetchone()["n"]
    return {
        "engine": "sqlite",
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "schema_version": SCHEMA_VERSION,
        "tables": tables,
        "upload_count": upload_count,
        "pk_count": pk_count,
        "audit_count": audit_count,
    }
