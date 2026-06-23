#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Temu 看板统一后端（单文件）
- 静态页面 + OSS 代理 /api/sync
- 协作 API /api/collab/*（用户/小组/PK 索引 → 全部存阿里云 OSS）
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import threading
import time
import uuid
from email.utils import formatdate
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

import collab_db

PORT = int(os.environ.get("TEMU_API_PORT", "8080"))
PROXY_PATH = "/__temu_oss__"
SYNC_API_PATH = "/api/sync"
STATUS_API_PATH = "/api/status"
COLLAB_PREFIX = "/api/collab"

JWT_TTL_SEC = 7 * 24 * 3600
PBKDF2_ROUNDS = 120_000

DEFAULT_GROUPS = [
    {"id": "g1", "name": "一组"},
    {"id": "g2", "name": "二组"},
    {"id": "g3", "name": "三组"},
    {"id": "g4", "name": "四组"},
]


# ── .env ─────────────────────────────────────────────────────────────

def load_env_file(path: str, force: bool = False) -> None:
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if not key:
                continue
            if force and (key.startswith("TEMU_OSS_") or key.startswith("TEMU_JWT") or key.startswith("TEMU_COLLAB")):
                os.environ[key] = val
            elif key not in os.environ:
                os.environ[key] = val


def write_env_file(ak: str, sk: str, bucket: str, region: str, prefix: str) -> str:
    env_path = os.path.join(os.getcwd(), ".env")
    prefix = prefix if prefix.endswith("/") else prefix + "/"
    lines = [
        "# Temu 看板 OSS Key（本地托管，勿提交 Git / 勿外传）",
        f"TEMU_OSS_ACCESS_KEY_ID={ak}",
        f"TEMU_OSS_ACCESS_KEY_SECRET={sk}",
        f"TEMU_OSS_BUCKET={bucket}",
        f"TEMU_OSS_REGION={normalize_region(region)}",
        f"TEMU_OSS_PREFIX={prefix}",
        "",
    ]
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    load_env_file(env_path, force=True)
    return env_path


def jwt_secret() -> str:
    s = os.environ.get("TEMU_JWT_SECRET", "").strip()
    if not s:
        s = secrets.token_hex(32)
        os.environ["TEMU_JWT_SECRET"] = s
        sys.stdout.write("[协作] 未配置 TEMU_JWT_SECRET，已生成本次会话临时密钥（重启后 token 失效）\n")
    return s


# ── OSS ──────────────────────────────────────────────────────────────

def normalize_region(region: str) -> str:
    r = (region or "").strip()
    if not r:
        return r
    if r.startswith("oss-"):
        return r
    if r.startswith("cn-"):
        return "oss-" + r
    return r


def get_server_oss_cfg() -> dict | None:
    ak = os.environ.get("TEMU_OSS_ACCESS_KEY_ID", "").strip()
    sk = os.environ.get("TEMU_OSS_ACCESS_KEY_SECRET", "").strip()
    bucket = os.environ.get("TEMU_OSS_BUCKET", "").strip()
    region = os.environ.get("TEMU_OSS_REGION", "oss-cn-hangzhou").strip()
    prefix = os.environ.get("TEMU_OSS_PREFIX", "temu/").strip()
    if not prefix.endswith("/"):
        prefix += "/"
    if not all([ak, sk, bucket, region]):
        return None
    return {
        "accessKeyId": ak,
        "accessKeySecret": sk,
        "bucket": bucket,
        "region": region,
        "prefix": prefix,
    }


def oss_host(cfg: dict) -> str:
    return f"{cfg['bucket']}.{normalize_region(cfg.get('region', ''))}.aliyuncs.com"


def oss_put(cfg: dict, key: str, body_str: str) -> None:
    bucket = cfg["bucket"]
    host = oss_host(cfg)
    url = f"https://{host}/{key}"
    content_type = "application/json; charset=utf-8"
    body = body_str.encode("utf-8")
    date = formatdate(timeval=None, localtime=False, usegmt=True)
    resource = f"/{bucket}/{key}"
    string_to_sign = f"PUT\n\n{content_type}\n{date}\n{resource}"
    sig = base64.b64encode(
        hmac.new(
            cfg["accessKeySecret"].encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha1,
        ).digest()
    ).decode("ascii")
    req = Request(url, data=body, method="PUT")
    req.add_header("Content-Type", content_type)
    req.add_header("Date", date)
    req.add_header("Authorization", f"OSS {cfg['accessKeyId']}:{sig}")
    with urlopen(req, timeout=60) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"HTTP {resp.status}")


def oss_get_signed(cfg: dict, key: str) -> str:
    bucket = cfg["bucket"]
    host = oss_host(cfg)
    url = f"https://{host}/{key}"
    date = formatdate(timeval=None, localtime=False, usegmt=True)
    resource = f"/{bucket}/{key}"
    string_to_sign = f"GET\n\n\n{date}\n{resource}"
    sig = base64.b64encode(
        hmac.new(
            cfg["accessKeySecret"].encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha1,
        ).digest()
    ).decode("ascii")
    req = Request(url, method="GET")
    req.add_header("Date", date)
    req.add_header("Authorization", f"OSS {cfg['accessKeyId']}:{sig}")
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except HTTPError as e:
        if e.code == 404:
            raise FileNotFoundError(key) from e
        body = e.read().decode("utf-8", errors="replace")[:240]
        raise RuntimeError(f"HTTP {e.code}: {body}") from e


def collab_key(cfg: dict, name: str) -> str:
    return f"{cfg['prefix']}collab/{name}"


def oss_read_json(cfg: dict, key: str, default=None):
    try:
        return json.loads(oss_get_signed(cfg, key))
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default


def oss_write_json(cfg: dict, key: str, data) -> None:
    oss_put(cfg, key, json.dumps(data, ensure_ascii=False, separators=(",", ":")))


# ── 密码 / JWT（标准库）────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return f"{salt.hex()}:{dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(dk_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
        return hmac.compare_digest(dk, expected)
    except (ValueError, TypeError):
        return False


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def make_jwt(payload: dict) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = payload.copy()
    body["exp"] = int(time.time()) + JWT_TTL_SEC
    body_b64 = _b64url(json.dumps(body, separators=(",", ":")).encode())
    sig = hmac.new(
        jwt_secret().encode(),
        f"{header}.{body_b64}".encode(),
        hashlib.sha256,
    ).digest()
    return f"{header}.{body_b64}.{_b64url(sig)}"


def parse_jwt(token: str) -> dict | None:
    try:
        header_b64, body_b64, sig_b64 = token.split(".", 2)
        expected = hmac.new(
            jwt_secret().encode(),
            f"{header_b64}.{body_b64}".encode(),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_b64url(expected), sig_b64):
            return None
        payload = json.loads(_b64url_decode(body_b64))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except (ValueError, json.JSONDecodeError, TypeError):
        return None


def slugify(name: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "-", (name or "").strip())
    return s.strip("-") or "user"


# ── 协作域 OSS 读写 ──────────────────────────────────────────────────

def ensure_collab_bootstrap(cfg: dict) -> None:
    meta_key = collab_key(cfg, "meta.json")
    if oss_read_json(cfg, meta_key):
        return
    org_id = str(uuid.uuid4())
    meta = {
        "version": 1,
        "org_id": org_id,
        "org_name": "Temu运营部",
        "dept_name": "运营部（单部门）",
        "initialized_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    groups = {"version": 1, "groups": DEFAULT_GROUPS}
    invites = {
        "version": 1,
        "codes": [
            {
                "code": os.environ.get("TEMU_COLLAB_OPS_INVITE", "TEMU-OPS-2026"),
                "role": "operator",
                "max_uses": 30,
                "used": 0,
                "group_id": None,
                "note": "运营组员注册",
            },
            {
                "code": os.environ.get("TEMU_COLLAB_LEAD_INVITE", "TEMU-LEAD-2026"),
                "role": "supervisor",
                "max_uses": 8,
                "used": 0,
                "group_id": None,
                "note": "小组主管 / 组长",
            },
            {
                "code": os.environ.get("TEMU_COLLAB_ADMIN_INVITE", "TEMU-ADMIN-2026"),
                "role": "admin",
                "max_uses": 3,
                "used": 0,
                "group_id": None,
                "note": "管理员",
            },
        ],
    }
    oss_write_json(cfg, meta_key, meta)
    oss_write_json(cfg, collab_key(cfg, "groups.json"), groups)
    oss_write_json(cfg, collab_key(cfg, "invites.json"), invites)
    oss_write_json(cfg, collab_key(cfg, "accounts_index.json"), {"version": 1, "users": []})
    oss_write_json(cfg, collab_key(cfg, "pk_latest.json"), {"version": 1, "updated_at": None, "entries": {}})
    oss_write_json(cfg, collab_key(cfg, "upload_log.json"), {"version": 1, "items": []})
    sys.stdout.write("[协作] 已在 OSS 初始化组织数据（单部门 · 四个小组）\n")
    for c in invites["codes"]:
        sys.stdout.write(f"         邀请码 {c['code']} → {c['role']} ({c['note']})\n")


def load_groups_map(cfg: dict) -> dict[str, str]:
    data = oss_read_json(cfg, collab_key(cfg, "groups.json"), {"groups": DEFAULT_GROUPS})
    return {g["id"]: g["name"] for g in data.get("groups", DEFAULT_GROUPS)}


def find_user_by_name(cfg: dict, display_name: str) -> dict | None:
    idx = oss_read_json(cfg, collab_key(cfg, "accounts_index.json"), {"users": []})
    name = (display_name or "").strip()
    for u in idx.get("users", []):
        if u.get("display_name") == name:
            uid = u["id"]
            full = oss_read_json(cfg, collab_key(cfg, f"users/{uid}.json"))
            return full
    return None


def save_user(cfg: dict, user: dict) -> None:
    uid = user["id"]
    oss_write_json(cfg, collab_key(cfg, f"users/{uid}.json"), user)
    idx = oss_read_json(cfg, collab_key(cfg, "accounts_index.json"), {"version": 1, "users": []})
    users = [u for u in idx.get("users", []) if u.get("id") != uid]
    users.append({
        "id": uid,
        "display_name": user["display_name"],
        "group_id": user.get("group_id"),
        "role": user.get("role", "operator"),
        "status": user.get("status", "active"),
    })
    oss_write_json(cfg, collab_key(cfg, "accounts_index.json"), {"version": 1, "users": users})


def consume_invite(cfg: dict, code: str) -> dict | None:
    data = oss_read_json(cfg, collab_key(cfg, "invites.json"), {"codes": []})
    for inv in data.get("codes", []):
        if inv.get("code") != code:
            continue
        if inv.get("used", 0) >= inv.get("max_uses", 1):
            return None
        inv["used"] = inv.get("used", 0) + 1
        oss_write_json(cfg, collab_key(cfg, "invites.json"), data)
        return inv
    return None


def auth_user_from_header(handler: SimpleHTTPRequestHandler) -> dict | None:
    auth = handler.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    payload = parse_jwt(auth[7:].strip())
    if not payload or not payload.get("sub"):
        return None
    cfg = get_server_oss_cfg()
    if not cfg:
        return None
    user = oss_read_json(cfg, collab_key(cfg, f"users/{payload['sub']}.json"))
    if not user or user.get("status") != "active":
        return None
    return user


# ── 协作 API 逻辑 ────────────────────────────────────────────────────

def collab_register(cfg: dict, body: dict) -> dict:
    invite_code = str(body.get("invite_code", "")).strip()
    display_name = str(body.get("display_name", "")).strip()
    password = str(body.get("password", ""))
    group_id = str(body.get("group_id", "")).strip()
    if not invite_code or not display_name or len(password) < 6:
        raise ValueError("需要 invite_code、display_name、password(≥6)，以及 group_id")
    groups = load_groups_map(cfg)
    if group_id not in groups:
        raise ValueError("无效的小组，请从 /api/collab/groups 选择")
    if find_user_by_name(cfg, display_name):
        raise ValueError("该姓名已注册，请换一个显示名或联系主管")
    inv = consume_invite(cfg, invite_code)
    if not inv:
        raise ValueError("邀请码无效或已用完")
    role = inv.get("role", "operator")
    if inv.get("group_id") and inv["group_id"] != group_id and role == "operator":
        raise ValueError("该邀请码绑定了其他小组")
    meta = oss_read_json(cfg, collab_key(cfg, "meta.json"), {})
    user = {
        "id": str(uuid.uuid4()),
        "org_id": meta.get("org_id", ""),
        "display_name": display_name,
        "group_id": group_id,
        "group_name": groups[group_id],
        "role": role,
        "status": "active",
        "password_hash": hash_password(password),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    save_user(cfg, user)
    collab_db.record_audit("collab_register", user, {"group_id": group_id, "role": role})
    token = make_jwt({"sub": user["id"], "role": role, "group_id": group_id})
    return {
        "ok": True,
        "token": token,
        "user": {
            "id": user["id"],
            "display_name": display_name,
            "group_id": group_id,
            "group_name": groups[group_id],
            "role": role,
        },
    }


def collab_login(cfg: dict, body: dict) -> dict:
    display_name = str(body.get("display_name", "")).strip()
    password = str(body.get("password", ""))
    user = find_user_by_name(cfg, display_name)
    if not user or not verify_password(password, user.get("password_hash", "")):
        raise ValueError("姓名或密码错误")
    collab_db.record_audit("collab_login", user, {"group_id": user.get("group_id")})
    token = make_jwt({
        "sub": user["id"],
        "role": user.get("role", "operator"),
        "group_id": user.get("group_id"),
    })
    return {
        "ok": True,
        "token": token,
        "user": {
            "id": user["id"],
            "display_name": user["display_name"],
            "group_id": user.get("group_id"),
            "group_name": user.get("group_name"),
            "role": user.get("role", "operator"),
        },
    }


def collab_permissions(user: dict) -> dict:
    """Role capability map consumed by the admin console."""
    role = user.get("role", "operator")
    is_supervisor = role in ("supervisor", "admin")
    is_admin = role == "admin"
    return {
        "ok": True,
        "role": role,
        "permissions": {
            "local_save": True,
            "view_logs": True,
            "export_weekly": True,
            "collab_sync": is_supervisor,
            "team_benchmark": is_supervisor,
            "team_pk_board": is_supervisor,
            "sync_config": is_admin,
            "sync_test": is_admin,
            "clear_local": is_admin,
        },
    }


def collab_upload(cfg: dict, user: dict, body: dict) -> dict:
    summary = body.get("summary")
    if not summary or not isinstance(summary, dict):
        raise ValueError("缺少 summary")
    if int(summary.get("version", 0)) < 2:
        raise ValueError("summary.version 须 ≥ 2（含 pk_snapshot）")
    pk = summary.get("pk_snapshot")
    if not pk or "align_score" not in pk:
        raise ValueError("缺少 pk_snapshot.align_score")
    uid = user["id"]
    summary["user_id"] = uid
    summary["display_name"] = user["display_name"]
    summary["group_id"] = user.get("group_id")
    summary["group_name"] = user.get("group_name")
    date = summary.get("date") or time.strftime("%Y-%m-%d")
    ts = int(time.time() * 1000)
    key = f"{cfg['prefix']}uploads/{uid}/{date}/{ts}.json"
    oss_write_json(cfg, key, summary)
    groups = load_groups_map(cfg)
    gname = groups.get(user.get("group_id", ""), user.get("group_name", ""))
    entry = {
        "user_id": uid,
        "display_name": user["display_name"],
        "group_id": user.get("group_id"),
        "group_name": gname,
        "summary_date": date,
        "oss_key": key,
        "align_score": int(pk.get("align_score", 0)),
        "score_label": pk.get("score_label", ""),
        "gold_pct": pk.get("gold_pct"),
        "avg_margin": pk.get("avg_margin"),
        "roas": pk.get("roas"),
        "avg_day_sales": pk.get("avg_day_sales"),
        "spu_count": len(summary.get("products") or []),
        "store_count": len(summary.get("store_records") or []),
        "uploaded_at": summary.get("uploaded_at") or time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    pk_data = oss_read_json(cfg, collab_key(cfg, "pk_latest.json"), {"version": 1, "entries": {}})
    pk_data.setdefault("entries", {})[uid] = entry
    pk_data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    oss_write_json(cfg, collab_key(cfg, "pk_latest.json"), pk_data)
    log = oss_read_json(cfg, collab_key(cfg, "upload_log.json"), {"version": 1, "items": []})
    log.setdefault("items", []).append({
        "user_id": uid,
        "display_name": user["display_name"],
        "oss_key": key,
        "at": entry["uploaded_at"],
    })
    if len(log["items"]) > 500:
        log["items"] = log["items"][-500:]
    oss_write_json(cfg, collab_key(cfg, "upload_log.json"), log)
    collab_db.record_upload(entry)
    collab_db.record_audit("collab_upload", user, {
        "oss_key": key,
        "align_score": entry.get("align_score"),
        "spu_count": entry.get("spu_count"),
        "store_count": entry.get("store_count"),
    })
    return {"ok": True, "key": key, "entry": entry}


def collab_uploads_recent(cfg: dict, user: dict, limit: int = 20) -> dict:
    """Recent summary uploads, scoped by role for the admin console."""
    limit = max(1, min(int(limit or 20), 100))
    role = user.get("role", "operator")
    group_id = user.get("group_id")

    def allowed(item: dict) -> bool:
        uid = item.get("user_id")
        if role == "operator":
            return uid == user["id"]
        if role == "supervisor":
            return item.get("group_id") == group_id or uid == user["id"]
        return True

    try:
        db_items = []
        for item in collab_db.recent_uploads(100):
            if not allowed(item):
                continue
            db_items.append(item)
            if len(db_items) >= limit:
                break
        if db_items:
            return {
                "ok": True,
                "role": role,
                "source": "sqlite",
                "count": len(db_items),
                "items": db_items,
            }
    except Exception as exc:
        print(f"[DB] recent uploads fallback to OSS: {exc}")

    log = oss_read_json(cfg, collab_key(cfg, "upload_log.json"), {"version": 1, "items": []})
    pk_data = oss_read_json(cfg, collab_key(cfg, "pk_latest.json"), {"entries": {}})
    latest_by_user = pk_data.get("entries") or {}
    items = []
    for item in reversed(log.get("items", [])):
        uid = item.get("user_id")
        latest = latest_by_user.get(uid, {})
        scoped = {
            "user_id": uid,
            "display_name": item.get("display_name", ""),
            "group_id": latest.get("group_id"),
            "group_name": latest.get("group_name", ""),
            "at": item.get("at"),
            "oss_key": item.get("oss_key"),
            "align_score": latest.get("align_score"),
            "spu_count": latest.get("spu_count"),
            "store_count": latest.get("store_count"),
        }
        if not allowed(scoped):
            continue
        items.append(scoped)
        if len(items) >= limit:
            break
    return {"ok": True, "role": role, "source": "oss", "count": len(items), "items": items}


def collab_audit_recent(user: dict, limit: int = 20) -> dict:
    """Recent database audit events, filtered by the current role."""
    role = user.get("role", "operator")
    group_id = user.get("group_id")
    raw_items = collab_db.recent_audit(limit)
    items = []
    for item in raw_items:
        actor_id = item.get("actor_id")
        detail = item.get("detail") or {}
        if role == "operator" and actor_id != user["id"]:
            continue
        if role == "supervisor":
            item_group = detail.get("group_id")
            if item_group and item_group != group_id and actor_id != user["id"]:
                continue
            if not item_group and actor_id != user["id"]:
                continue
        if role != "admin" and not actor_id:
            continue
        items.append(item)
        if len(items) >= limit:
            break
    return {"ok": True, "role": role, "count": len(items), "items": items}


def collab_pk_board(cfg: dict, user: dict) -> dict:
    pk_data = oss_read_json(cfg, collab_key(cfg, "pk_latest.json"), {"entries": {}})
    entries = list((pk_data.get("entries") or {}).values())
    role = user.get("role", "operator")
    if role == "operator":
        entries = [e for e in entries if e.get("user_id") == user["id"]]
    entries.sort(key=lambda e: (-int(e.get("align_score", 0)), e.get("display_name", "")))
    groups = load_groups_map(cfg)
    by_group: dict[str, list] = {gid: [] for gid in groups}
    by_group["_unknown"] = []
    for e in entries:
        gid = e.get("group_id") or "_unknown"
        by_group.setdefault(gid, []).append(e)
    meta = oss_read_json(cfg, collab_key(cfg, "meta.json"), {})
    return {
        "ok": True,
        "org_name": meta.get("org_name", ""),
        "dept_name": meta.get("dept_name", ""),
        "role": role,
        "updated_at": pk_data.get("updated_at"),
        "members": entries,
        "by_group": [
            {"group_id": gid, "group_name": groups.get(gid, "未分组"), "members": by_group.get(gid, [])}
            for gid in groups
        ],
    }


def collab_benchmark(cfg: dict, user: dict) -> dict:
    """主管/全员选品基准：拉取他人最新摘要中的 products（不含自己）。"""
    pk_data = oss_read_json(cfg, collab_key(cfg, "pk_latest.json"), {"entries": {}})
    entries = list((pk_data.get("entries") or {}).values())
    my_id = user["id"]
    others = [e for e in entries if e.get("user_id") != my_id and e.get("oss_key")]
    products = []
    people = 0
    for e in others:
        try:
            s = oss_read_json(cfg, e["oss_key"])
        except Exception:
            continue
        if not s or not s.get("products"):
            continue
        people += 1
        products.extend(s["products"])
    return {"ok": True, "people": people, "count": len(products), "products": products}


def build_status_payload() -> dict:
    """Fast local health payload for the admin console; avoids OSS network I/O."""
    cfg = get_server_oss_cfg()
    return {
        "ok": True,
        "server": {
            "name": "temu-dashboard-api",
            "port": PORT,
            "cwd": os.getcwd(),
        },
        "oss": {
            "configured": bool(cfg),
            "bucket": cfg.get("bucket") if cfg else None,
            "region": normalize_region(cfg.get("region", "")) if cfg else None,
            "prefix": cfg.get("prefix") if cfg else None,
            "key_mode": "server-env" if cfg else "missing",
        },
        "database": collab_db.status(),
        "features": {
            "static_files": True,
            "sync_api": True,
            "collab_api": bool(cfg),
            "legacy_oss_proxy": True,
        },
        "routes": {
            "status": STATUS_API_PATH,
            "sync": SYNC_API_PATH,
            "collab": f"{COLLAB_PREFIX}/*",
            "collab_permissions": f"{COLLAB_PREFIX}/permissions",
            "legacy_proxy": PROXY_PATH,
        },
    }


# ── HTTP Handler ─────────────────────────────────────────────────────

class TemuHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == STATUS_API_PATH:
            self._json_response(HTTPStatus.OK, build_status_payload())
            return
        if path.startswith(COLLAB_PREFIX):
            self._handle_collab_get(path)
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw.decode("utf-8") or "{}") if raw else {}
        except json.JSONDecodeError:
            self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid json"})
            return

        if path.startswith(COLLAB_PREFIX):
            self._handle_collab_post(path, payload)
            return
        if path not in (PROXY_PATH, SYNC_API_PATH):
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return
        if path == SYNC_API_PATH:
            self._handle_api_sync(payload)
            return
        self._handle_legacy_oss_proxy(payload)

    def _handle_collab_get(self, path: str) -> None:
        cfg = get_server_oss_cfg()
        if not cfg:
            self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "服务端未配置 OSS"})
            return
        try:
            ensure_collab_bootstrap(cfg)
        except Exception as e:
            self._json_response(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": f"协作初始化失败: {e}"})
            return

        if path == f"{COLLAB_PREFIX}/ping":
            meta = oss_read_json(cfg, collab_key(cfg, "meta.json"), {})
            self._json_response(HTTPStatus.OK, {"ok": True, "collab": True, "org_name": meta.get("org_name")})
            return

        if path == f"{COLLAB_PREFIX}/groups":
            data = oss_read_json(cfg, collab_key(cfg, "groups.json"), {"groups": DEFAULT_GROUPS})
            self._json_response(HTTPStatus.OK, {"ok": True, "groups": data.get("groups", DEFAULT_GROUPS)})
            return

        user = auth_user_from_header(self)
        if path == f"{COLLAB_PREFIX}/me":
            if not user:
                self._json_response(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "未登录"})
                return
            self._json_response(HTTPStatus.OK, {
                "ok": True,
                "user": {
                    "id": user["id"],
                    "display_name": user["display_name"],
                    "group_id": user.get("group_id"),
                    "group_name": user.get("group_name"),
                    "role": user.get("role"),
                },
            })
            return

        if path == f"{COLLAB_PREFIX}/permissions":
            if not user:
                self._json_response(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "not logged in"})
                return
            self._json_response(HTTPStatus.OK, collab_permissions(user))
            return

        if path == f"{COLLAB_PREFIX}/team/pk-board":
            if not user:
                self._json_response(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "未登录"})
                return
            try:
                self._json_response(HTTPStatus.OK, collab_pk_board(cfg, user))
            except Exception as e:
                self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(e)})
            return

        if path == f"{COLLAB_PREFIX}/team/benchmark":
            if not user:
                self._json_response(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "未登录"})
                return
            try:
                self._json_response(HTTPStatus.OK, collab_benchmark(cfg, user))
            except Exception as e:
                self._json_response(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(e)})
            return

        if path == f"{COLLAB_PREFIX}/uploads/recent":
            if not user:
                self._json_response(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "未登录"})
                return
            query = parse_qs(urlparse(self.path).query)
            try:
                limit = int((query.get("limit") or ["20"])[0])
            except (TypeError, ValueError):
                limit = 20
            try:
                self._json_response(HTTPStatus.OK, collab_uploads_recent(cfg, user, limit))
            except Exception as e:
                self._json_response(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(e)})
            return

        if path == f"{COLLAB_PREFIX}/audit/recent":
            if not user:
                self._json_response(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "not logged in"})
                return
            query = parse_qs(urlparse(self.path).query)
            try:
                limit = int((query.get("limit") or ["20"])[0])
            except (TypeError, ValueError):
                limit = 20
            try:
                self._json_response(HTTPStatus.OK, collab_audit_recent(user, limit))
            except Exception as e:
                self._json_response(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(e)})
            return

        self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "unknown collab route"})

    def _handle_collab_post(self, path: str, payload: dict) -> None:
        cfg = get_server_oss_cfg()
        if not cfg:
            self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "服务端未配置 OSS"})
            return
        try:
            ensure_collab_bootstrap(cfg)
        except Exception as e:
            self._json_response(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": f"协作初始化失败: {e}"})
            return

        try:
            if path == f"{COLLAB_PREFIX}/register":
                self._json_response(HTTPStatus.OK, collab_register(cfg, payload))
                return
            if path == f"{COLLAB_PREFIX}/login":
                self._json_response(HTTPStatus.OK, collab_login(cfg, payload))
                return
            if path == f"{COLLAB_PREFIX}/upload":
                user = auth_user_from_header(self)
                if not user:
                    self._json_response(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "请先登录协作账号"})
                    return
                self._json_response(HTTPStatus.OK, collab_upload(cfg, user, payload))
                return
            self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "unknown collab route"})
        except ValueError as e:
            self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(e)})
        except Exception as e:
            self._json_response(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(e)})

    def _is_local_client(self) -> bool:
        return self.client_address[0] in ("127.0.0.1", "::1")

    def _handle_api_sync(self, payload: dict) -> None:
        action = payload.get("action", "ping")

        if action == "write-env":
            if not self._is_local_client():
                self._json_response(
                    HTTPStatus.FORBIDDEN,
                    {"ok": False, "error": "write-env 仅允许本机 localhost 调用"},
                )
                return
            ak = str(payload.get("accessKeyId") or "").strip()
            sk = str(payload.get("accessKeySecret") or "").strip()
            bucket = str(payload.get("bucket") or "temu-shujufenxi-data").strip()
            region = str(payload.get("region") or "oss-cn-hangzhou").strip()
            prefix = str(payload.get("prefix") or "temu/").strip()
            if not ak or not sk:
                self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "缺少 accessKeyId 或 accessKeySecret"})
                return
            try:
                write_env_file(ak, sk, bucket, region, prefix)
                cfg = get_server_oss_cfg()
                if cfg:
                    ensure_collab_bootstrap(cfg)
                self._json_response(HTTPStatus.OK, {
                    "ok": True,
                    "written": True,
                    "bucket": bucket,
                    "region": normalize_region(region),
                    "prefix": prefix if prefix.endswith("/") else prefix + "/",
                    "collab": True,
                })
            except Exception as e:
                self._json_response(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(e)})
            return

        if payload.get("accessKeySecret") or (payload.get("cfg") or {}).get("accessKeySecret"):
            self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "C0-1: 请求体不得含 accessKeySecret"})
            return

        if action == "ping":
            cfg = get_server_oss_cfg()
            if not cfg:
                self._json_response(HTTPStatus.OK, {
                    "ok": False,
                    "serverSync": False,
                    "error": "服务端未配置 OSS（复制 .env.example 为 .env 并填写 Key）",
                })
                return
            try:
                ensure_collab_bootstrap(cfg)
            except Exception:
                pass
            self._json_response(HTTPStatus.OK, {
                "ok": True,
                "serverSync": True,
                "collab": True,
                "version": 2,
                "bucket": cfg["bucket"],
                "region": normalize_region(cfg["region"]),
                "prefix": cfg.get("prefix", "temu/"),
            })
            return

        cfg = get_server_oss_cfg()
        if not cfg:
            self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "服务端未配置 OSS Key（见 .env.example）"})
            return

        key = payload.get("key", "")
        try:
            if action == "put":
                if not key:
                    raise ValueError("missing key")
                oss_put(cfg, key, payload.get("body", ""))
                self._json_response(HTTPStatus.OK, {"ok": True, "key": key})
                return
            if action == "get":
                if not key:
                    raise ValueError("missing key")
                text = oss_get_signed(cfg, key)
                self._json_response(HTTPStatus.OK, {"ok": True, "body": text})
                return
            self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"unknown action: {action}"})
        except HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:240] if hasattr(e, "read") else str(e)
            self._json_response(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": f"HTTP {e.code}: {detail}"})
        except URLError as e:
            self._json_response(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": f"网络错误: {e.reason}"})
        except Exception as e:
            self._json_response(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(e)})

    def _handle_legacy_oss_proxy(self, payload: dict) -> None:
        action = payload.get("action", "put")
        cfg = payload.get("cfg") or {}
        key = payload.get("key", "")

        if action == "ping":
            self._json_response(HTTPStatus.OK, {"ok": True, "proxy": True, "version": 1})
            return

        missing = [k for k in ("bucket", "region", "accessKeyId", "accessKeySecret") if not cfg.get(k)]
        if missing:
            self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "OSS 配置不完整: " + ", ".join(missing)})
            return

        try:
            if action == "put":
                if not key:
                    raise ValueError("missing key")
                oss_put(cfg, key, payload.get("body", ""))
                self._json_response(HTTPStatus.OK, {"ok": True, "key": key})
                return
            if action == "get":
                if not key:
                    raise ValueError("missing key")
                text = oss_get_signed(cfg, key)
                self._json_response(HTTPStatus.OK, {"ok": True, "body": text})
                return
            self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"unknown action: {action}"})
        except Exception as e:
            self._json_response(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(e)})

    def _json_response(self, status: HTTPStatus, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        first = args[0] if args else ""
        if isinstance(first, str) and (PROXY_PATH in first or SYNC_API_PATH in first or COLLAB_PREFIX in first):
            sys.stdout.write("[API] %s\n" % first)
            return
        super().log_message(fmt, *args)


def main() -> None:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    load_env_file(os.path.join(os.getcwd(), ".env"))
    server_cfg = get_server_oss_cfg()
    server = HTTPServer(("0.0.0.0", PORT), TemuHandler)

    if server_cfg:
        def bootstrap_collab_async() -> None:
            try:
                ensure_collab_bootstrap(server_cfg)
            except Exception as e:
                sys.stdout.write(f"[协作] OSS 初始化跳过: {e}\n")

        threading.Thread(target=bootstrap_collab_async, daemon=True).start()

    print("")
    print("=" * 46)
    print("  Temu 看板 · api_server.py（单文件后端）")
    print(f"  目录: {os.getcwd()}")
    print("=" * 46)
    print("")
    print("浏览器打开:")
    print(f"  http://localhost:{PORT}/temu-dashboard.html")
    print("")
    if server_cfg:
        print(f"OSS Key 托管: 已启用 · {server_cfg['bucket']}")
        print("协作 API:     /api/collab/*（OSS 初始化后台进行）")
    else:
        print("OSS: 未配置（.env.example → .env）")
    print("")
    print("按 Ctrl+C 停止")
    print("")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")


if __name__ == "__main__":
    main()
