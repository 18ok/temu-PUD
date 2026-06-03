#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Temu 看板本地服务 + OSS 上传代理（绕过浏览器 CORS）。"""
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
        if self.path.split("?", 1)[0] != PROXY_PATH:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid json"})
            return

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
        if PROXY_PATH in (args[0] if args else ""):
            sys.stdout.write("[OSS代理] %s\n" % (args[0] if args else fmt))
            return
        super().log_message(fmt, *args)


def main() -> None:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    server = HTTPServer(("127.0.0.1", PORT), TemuHandler)
    print("")
    print("=" * 42)
    print("  Temu 看板本地服务（含 OSS 代理）")
    print(f"  目录: {os.getcwd()}")
    print("=" * 42)
    print("")
    print("浏览器打开:")
    print(f"  http://localhost:{PORT}/temu-dashboard.html")
    print("")
    print("云端同步走本地代理，无需配置 OSS 跨域 CORS。")
    print("按 Ctrl+C 停止服务")
    print("")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")


if __name__ == "__main__":
    main()
