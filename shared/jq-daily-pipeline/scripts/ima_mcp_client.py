#!/usr/bin/env python3
"""IMA MCP client — 直连 https://ima.qq.com/mcp (走 MCP 通道, 非 OpenAPI 降级)"""
import json
import subprocess
import sys

MCP_URL = "https://ima.qq.com/mcp"
TOKEN_FILE = "/tmp/ima_token.txt"


def _token():
    with open(TOKEN_FILE) as f:
        return f.read().strip()


_session = {"id": None}


def _rpc(method, params, _id=1, notify=False):
    payload = {"jsonrpc": "2.0", "method": method, "params": params}
    if not notify:
        payload["id"] = _id
    body = json.dumps(payload)
    cmd = [
        "curl", "-s", "-m", "60", "-X", "POST", MCP_URL,
        "-H", "Authorization: Bearer " + _token(),
        "-H", "Content-Type: application/json",
        "-H", "Accept: application/json, text/event-stream",
        "-H", "Mcp-Session-Id: " + (_session["id"] or ""),
        "-d", body,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    # SSE format: data: {...}
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            try:
                return json.loads(line[5:].strip())
            except Exception:
                continue
    if out.strip():
        try:
            return json.loads(out)
        except Exception:
            return {"_raw": out[:500]}
    return {"_raw": "", "_err": "empty response"}


def initialize():
    r = _rpc("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "workbuddy-agent", "version": "1.0"},
    })
    # session id comes from response header; try to capture separately
    return r


def tools_list():
    return _rpc("tools/list", {}, _id=2)


def call_tool(name, args, _id=3):
    return _rpc("tools/call", {"name": name, "arguments": args}, _id=_id)


def send_initialized():
    return _rpc("notifications/initialized", {}, notify=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "init":
        print(json.dumps(initialize(), ensure_ascii=False, indent=1))
    elif cmd == "list":
        print(json.dumps(tools_list(), ensure_ascii=False, indent=1))
    elif cmd == "call":
        name = sys.argv[2]
        args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        print(json.dumps(call_tool(name, args), ensure_ascii=False, indent=1))
    elif cmd == "session":
        # capture Mcp-Session-Id header
        out = subprocess.run([
            "curl", "-s", "-D", "-", "-o", "/dev/null", "-m", "30", "-X", "POST", MCP_URL,
            "-H", "Authorization: Bearer " + _token(),
            "-H", "Content-Type: application/json",
            "-H", "Accept: application/json, text/event-stream",
            "-d", json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                              "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                         "clientInfo": {"name": "wb", "version": "1.0"}}}),
        ], capture_output=True, text=True).stdout
        print(out)
