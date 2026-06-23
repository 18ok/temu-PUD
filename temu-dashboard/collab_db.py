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


SCHEMA_VERSION = 1


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
                    int(time.time()),
                ),
            )

    safe_call(_write)


def recent_uploads(limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    limit = max(1, min(int(limit or 20), 100))
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT user_id, display_name, group_id, group_name, oss_key,
                   align_score, score_label, spu_count, store_count, uploaded_at,
                   created_at
            FROM upload_index
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
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
        audit_count = conn.execute("SELECT COUNT(*) AS n FROM audit_logs").fetchone()["n"]
    return {
        "engine": "sqlite",
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "schema_version": SCHEMA_VERSION,
        "tables": tables,
        "upload_count": upload_count,
        "audit_count": audit_count,
    }
