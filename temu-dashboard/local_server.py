#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Temu 看板本地服务 + OSS 上传代理（绕过浏览器 CORS）+ Key 托管 /api/sync。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
from email.utils import formatdate
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PORT = 8080
PROXY_PATH = "/__temu_oss__"
SYNC_API_PATH = "/api/sync"


def load_env_file(path: str, force: bool = False) -> None:
    """简易 .env 加载（无第三方依赖）。force=True 时覆盖已有 TEMU_OSS_*。"""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if not key:
                continue
            if force and key.startswith("TEMU_OSS_"):
                os.environ[key] = val
            elif key not in os.environ:
                os.environ[key] = val


def write_env_file(ak: str, sk: str, bucket: str, region: str, prefix: str) -> str:
    """写入 .env（仅本机 migrate 流程调用）。"""
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


def get_server_oss_cfg() -> dict | None:
    """从环境变量读取 OSS 配置（阶段 0：Key 仅在此）。"""
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


def normalize_region(region: str) -> str:
    r = (region or "").strip()
    if not r:
        return r
    if r.startswith("oss-"):
        return r
    if r.startswith("cn-"):
        return "oss-" + r
    return r


def oss_host(cfg: dict) -> str:
    region = normalize_region(cfg.get("region", ""))
    bucket = cfg.get("bucket", "")
    return f"{bucket}.{region}.aliyuncs.com"


def oss_put(cfg: dict, key: str, body_str: str) -> None:
    region = normalize_region(cfg["region"])
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
    """私有 Bucket：带 Authorization 的 GET（不依赖公共读）。"""
    region = normalize_region(cfg["region"])
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
        body = e.read().decode("utf-8", errors="replace")[:240]
        raise RuntimeError(f"HTTP {e.code}: {body}") from e


class TemuHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path not in (PROXY_PATH, SYNC_API_PATH):
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid json"})
            return

        if path == SYNC_API_PATH:
            self._handle_api_sync(payload)
            return
        self._handle_legacy_oss_proxy(payload)

    def _is_local_client(self) -> bool:
        return self.client_address[0] in ("127.0.0.1", "::1")

    def _handle_api_sync(self, payload: dict) -> None:
        """阶段 0：Key 托管；常规 sync 请求体不得含 accessKeySecret（C0-1）。"""
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
                self._json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "缺少 accessKeyId 或 accessKeySecret"},
                )
                return
            try:
                write_env_file(ak, sk, bucket, region, prefix)
                sys.stdout.write("[OSS] .env 已写入（Key 托管 migrate）\n")
                self._json_response(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "written": True,
                        "bucket": bucket,
                        "region": normalize_region(region),
                        "prefix": prefix if prefix.endswith("/") else prefix + "/",
                    },
                )
            except Exception as e:
                self._json_response(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(e)})
            return

        if payload.get("accessKeySecret") or (payload.get("cfg") or {}).get("accessKeySecret"):
            self._json_response(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "C0-1: 请求体不得含 accessKeySecret"},
            )
            return

        if action == "ping":
            cfg = get_server_oss_cfg()
            if not cfg:
                self._json_response(
                    HTTPStatus.OK,
                    {
                        "ok": False,
                        "serverSync": False,
                        "error": "服务端未配置 OSS（复制 .env.example 为 .env 并填写 Key）",
                    },
                )
                return
            self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "serverSync": True,
                    "version": 1,
                    "bucket": cfg["bucket"],
                    "region": normalize_region(cfg["region"]),
                    "prefix": cfg.get("prefix", "temu/"),
                },
            )
            return

        cfg = get_server_oss_cfg()
        if not cfg:
            self._json_response(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "服务端未配置 OSS Key（见 .env.example）"},
            )
            return

        key = payload.get("key", "")
        try:
            if action == "put":
                body_str = payload.get("body", "")
                if not key:
                    raise ValueError("missing key")
                oss_put(cfg, key, body_str)
                self._json_response(HTTPStatus.OK, {"ok": True, "key": key})
                return
            if action == "get":
                if not key:
                    raise ValueError("missing key")
                text = oss_get_signed(cfg, key)
                self._json_response(HTTPStatus.OK, {"ok": True, "body": text})
                return
            self._json_response(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": f"unknown action: {action}"},
            )
        except HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:240] if hasattr(e, "read") else str(e)
            self._json_response(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": f"HTTP {e.code}: {detail}"})
        except URLError as e:
            self._json_response(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": f"网络错误: {e.reason}"})
        except Exception as e:
            self._json_response(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(e)})

    def _handle_legacy_oss_proxy(self, payload: dict) -> None:
        """旧版：浏览器传 cfg + Key（兼容未配置 .env 时）。"""
        action = payload.get("action", "put")
        cfg = payload.get("cfg") or {}
        key = payload.get("key", "")

        if action == "ping":
            self._json_response(HTTPStatus.OK, {"ok": True, "proxy": True, "version": 1})
            return

        missing = [k for k in ("bucket", "region", "accessKeyId", "accessKeySecret") if not cfg.get(k)]
        if missing:
            self._json_response(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "OSS 配置不完整: " + ", ".join(missing)},
            )
            return

        try:
            if action == "put":
                body_str = payload.get("body", "")
                if not key:
                    raise ValueError("missing key")
                oss_put(cfg, key, body_str)
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

    def _json_response(self, status: HTTPStatus, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        first = args[0] if args else ""
        if isinstance(first, str) and (PROXY_PATH in first or SYNC_API_PATH in first):
            sys.stdout.write("[OSS] %s\n" % first)
            return
        super().log_message(fmt, *args)


def main() -> None:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    load_env_file(os.path.join(os.getcwd(), ".env"))
    server_cfg = get_server_oss_cfg()
    server = HTTPServer(("0.0.0.0", PORT), TemuHandler)
    print("")
    print("=" * 42)
    print("  Temu 看板本地服务（含 OSS 代理）")
    print(f"  目录: {os.getcwd()}")
    print("=" * 42)
    print("")
    print("浏览器打开:")
    print(f"  http://localhost:{PORT}/temu-dashboard.html")
    print("")
    if server_cfg:
        print(f"Key 托管: 已启用 /api/sync · {server_cfg['bucket']}")
    else:
        print("Key 托管: 未配置（可选 .env.example → .env）")
        print("         未配置时仍可用浏览器内 AccessKey + /__temu_oss__ 代理")
    print("")
    print("按 Ctrl+C 停止服务")
    print("")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")


if __name__ == "__main__":
    main()
