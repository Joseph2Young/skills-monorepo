# MCP 连接器在 WorkBuddy 内使用指南

## 背景

`ima-daily-pipeline` 在 WorkBuddy 内运行时, 主人规则: **必须使用 IMA 连接器 (MCP/connector), 不允许降级到 HTTPS API**。

本文说明怎么在 WorkBuddy 内用 MCP 连接器跑流水线。

## 架构

```
┌────────────────────────────────────────────────────┐
│ WorkBuddy Agent (有 mcp__ima-mcp__* 工具)            │
│                                                    │
│  ┌──────────────────┐    启动       ┌────────────┐ │
│  │ step2/6 脚本      │───HTTP───────│ mcp_wrapper │ │
│  │  (Python 进程)   │   8765        │ (HTTP srv)  │ │
│  └──────────────────┘              └────────────┘ │
│         │                              │ 文件队列   │
│         │ mcp_callback.py              │ /tmp/...  │
│         │ (HTTP client)                ▼           │
│         │                          ┌────────────┐  │
│         │  响应                     │  Agent 主线 │  │
│         ◀──────────────────────────│ 程轮询队列  │  │
│                                    │ + 调 MCP   │  │
│                                    └────────────┘  │
└────────────────────────────────────────────────────┘
```

## WorkBuddy Agent 使用步骤

### 1. 启动 mcp_wrapper (HTTP server + 文件队列)

```bash
python3 ~/.workbuddy/skills/jq-daily-pipeline/scripts/mcp_wrapper.py \
  --port 8765 \
  --queue-dir /tmp/ima_mcp_queue
```

这条命令会:
- 监听 `http://127.0.0.1:8765/call`
- 收到请求后写到 `/tmp/ima_mcp_queue/in/{req_id}.json`
- 等 `/tmp/ima_mcp_queue/out/{req_id}.json` 出现后返回响应

### 2. 启动文件队列监控 (agent 端持续轮询)

Agent 需要持续监控 `/tmp/ima_mcp_queue/in/`, 对每个请求:
- 解析 server/method/params
- 调对应 MCP 工具 (`mcp__ima-mcp__*`)
- 把结果写到 `/tmp/ima_mcp_queue/out/{req_id}.json`

agent 端的轮询伪代码:
```python
while True:
    for req_file in glob("/tmp/ima_mcp_queue/in/*.json"):
        req = json.load(req_file)
        # 路由到对应 MCP 工具
        if req["method"] == "/openapi/wiki/v1/get_knowledge_list":
            result = mcp__ima_mcp__get_knowledge_list(**req["params"])
        # ...
        # 写响应
        out_file = req_file.parent.parent / "out" / (req_file.stem + ".json")
        out_file.write_text(json.dumps(result))
        req_file.unlink()
```

### 3. 设置环境变量跑流水线

```bash
export IMA_MCP_CALLBACK=~/.workbuddy/skills/jq-daily-pipeline/scripts/mcp_callback.py
export IMA_MCP_WRAPPER_URL=http://127.0.0.1:8765/call
export WORKBUDDY_REQUIRE_CONNECTOR=1
export JQS=/opt/miniconda3/bin/jqcli    # 或你电脑上的 jqcli 路径

python3 ~/.workbuddy/skills/jq-daily-pipeline/scripts/run_daily.sh
```

### 4. 完成后关 wrapper

```bash
# 找 PID
lsof -i :8765
kill <PID>
```

## 简化模式 (WorkBuddy Agent 推荐)

实际在 WorkBuddy Agent 内, 可以跳过 wrapper HTTP server, **直接用文件队列**:

```bash
# 1. 让 mcp_callback.py 直接读 /tmp/ima_mcp_queue/ 而不是 HTTP
#    (修改 mcp_callback.py, 加 IMA_MCP_QUEUE_MODE=1 分支)

# 2. Agent 端在跑 step 前/后, 用 DeferExecuteTool 处理队列:
#    跑 step 前: 清空队列目录
#    跑 step 中: 持续 DeferExecuteTool mcp__ima-mcp__* 处理请求
#    跑 step 后: 确认队列为空
```

这种模式更简单, 不需要额外的 HTTP server 进程。

## 故障排查

**Q: wrapper 启动后脚本还是报 "WorkBuddy 内必须使用 IMA 连接器"**
A: 检查:
   1. `echo $IMA_MCP_CALLBACK` 是否设置
   2. `echo $WORKBUDDY_REQUIRE_CONNECTOR` 是否 = 1
   3. callback 文件能 import: `python3 $IMA_MCP_CALLBACK` (不应报错)

**Q: wrapper 报 "timeout after 60s"**
A: agent 端没及时处理文件队列。检查:
   1. mcp 工具是否可用: WorkBuddy 应该有 `mcp__ima-mcp__*` 工具
   2. agent 监控循环是否在跑
   3. /tmp/ima_mcp_queue/in/ 是否有积压

**Q: 想降级到 HTTPS (非 WorkBuddy 环境)**
A: 取消 `WORKBUDDY_REQUIRE_CONNECTOR`, 脚本会自动降级。但主人规则禁止在 WorkBuddy 内降级。