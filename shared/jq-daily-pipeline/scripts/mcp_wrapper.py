#!/usr/bin/env python3
"""
IMA MCP wrapper 服务 (HTTP server)

这个 wrapper 是 mcp_callback.py 的对端。它接收 HTTP POST 请求, 把请求转换
成 MCP 工具调用, 然后返回响应。

由于普通 Python 进程无法直接调 MCP 工具, 这个 wrapper 提供了"把请求写到
文件队列"的 fallback 模式 —— 由 agent 端监控 /tmp/ima_mcp_queue/in/,
用 DeferExecuteTool 调 mcp__ima-mcp__*, 写回 /tmp/ima_mcp_queue/out/。

用法 (agent 端):
  python3 mcp_wrapper.py --port 8765 --queue-dir /tmp/ima_mcp_queue
  → 启动 HTTP server 在 8765 端口
  → 文件队列模式: 收到请求写到 in/, 等 out/ 出现响应后返回

或在 WorkBuddy agent 里直接接管 wrapper 逻辑:
  - 跳过 HTTP server, 直接用文件队列
  - agent 跑 step2/6 前, 后台监控 in/ 目录
  - 收到请求后调 DeferExecuteTool, 写回 out/

本脚本提供的 HTTP server 适合"agent 是 subagent / 独立进程"的场景。
"""
import argparse
import http.server
import json
import os
import socketserver
import sys
import time
from pathlib import Path


class QueueBasedHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler — 把请求写到文件队列, 等响应"""

    queue_dir: Path = None
    timeout_s: int = 60

    def do_POST(self):
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8")
            req = json.loads(body)
        except Exception as e:
            self._send(400, {"error": f"bad request: {e}"})
            return

        req_id = f"{time.time_ns()}"
        in_path = self.queue_dir / "in" / f"{req_id}.json"
        out_path = self.queue_dir / "out" / f"{req_id}.json"
        in_path.write_text(json.dumps(req, ensure_ascii=False), encoding="utf-8")

        # 等响应 (由 agent 端处理后写入)
        deadline = time.time() + self.timeout_s
        while time.time() < deadline:
            if out_path.exists():
                resp = json.loads(out_path.read_text(encoding="utf-8"))
                out_path.unlink()
                in_path.unlink(missing_ok=True)
                self._send(200, resp)
                return
            time.sleep(0.05)

        # 超时
        in_path.unlink(missing_ok=True)
        self._send(504, {"error": f"timeout after {self.timeout_s}s, agent 未响应"})

    def _send(self, status: int, body: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        sys.stderr.write(f"[mcp_wrapper] {format % args}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--queue-dir", default="/tmp/ima_mcp_queue")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    queue_dir = Path(args.queue_dir)
    (queue_dir / "in").mkdir(parents=True, exist_ok=True)
    (queue_dir / "out").mkdir(parents=True, exist_ok=True)

    QueueBasedHandler.queue_dir = queue_dir
    QueueBasedHandler.timeout_s = args.timeout

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", args.port), QueueBasedHandler) as httpd:
        print(f"[mcp_wrapper] listening on http://127.0.0.1:{args.port}", flush=True)
        print(f"[mcp_wrapper] queue dir: {queue_dir}", flush=True)
        print(f"[mcp_wrapper] agent should monitor {queue_dir}/in/ and write to {queue_dir}/out/", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[mcp_wrapper] shutting down...")


if __name__ == "__main__":
    main()