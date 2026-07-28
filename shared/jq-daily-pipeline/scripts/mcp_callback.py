#!/usr/bin/env python3
"""
MCP callback for IMA — WorkBuddy 内首选方式

这个文件被 IMA_MCP_CALLBACK 环境变量指向, 提供 call_mcp(server, method, params) 函数。
脚本通过它把 IMA OpenAPI 请求转发到 MCP 工具 (mcp__ima-mcp__*)。

实现: HTTP 客户端 → 调本地 wrapper 服务 (mcp_wrapper.py)
wrapper 服务负责把请求路由到 agent 的 MCP 工具, 然后返回响应。

用法:
  1) agent 端启动 wrapper:  python3 mcp_wrapper.py --port 8765
  2) 设置环境变量:
       export IMA_MCP_CALLBACK=/path/to/mcp_callback.py
       export IMA_MCP_WRAPPER_URL=http://127.0.0.1:8765
       export WORKBUDDY_REQUIRE_CONNECTOR=1
  3) 跑流水线:  python3 step2_ima_dedup.py
"""
import json
import os
import urllib.request
import urllib.error


def call_mcp(server: str, method: str, params: dict) -> dict:
    """调用 MCP 工具 — 通过 HTTP 调 wrapper

    Args:
        server:  MCP 服务器名 (IMA 用 "ima")
        method:  OpenAPI 路径, 如 "/openapi/wiki/v1/get_knowledge_list"
        params:  请求参数 dict

    Returns:
        MCP 工具返回的 dict (已是 IMA OpenAPI 响应格式)
    """
    wrapper_url = os.environ.get(
        "IMA_MCP_WRAPPER_URL", "http://127.0.0.1:8765/call"
    )

    payload = json.dumps({
        "server": server,
        "method": method,
        "params": params,
    }).encode("utf-8")

    req = urllib.request.Request(
        wrapper_url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"无法连接 IMA MCP wrapper ({wrapper_url}): {e}\n"
            f"请先启动 wrapper: python3 mcp_wrapper.py --port 8765"
        ) from e


# 可选: 自测
if __name__ == "__main__":
    print("=== mcp_callback 自测 ===")
    print(f"wrapper URL: {os.environ.get('IMA_MCP_WRAPPER_URL', 'http://127.0.0.1:8765/call')}")
    try:
        result = call_mcp("ima", "/openapi/wiki/v1/get_addable_knowledge_base_list", {})
        print(f"✅ MCP 调用成功: {json.dumps(result, ensure_ascii=False)[:200]}")
    except Exception as e:
        print(f"❌ {e}")