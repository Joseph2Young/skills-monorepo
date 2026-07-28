# IMA Connector 检测与降级

## 设计原则

**WorkBuddy 内强制走连接器**（MCP 优先, connector 备选）; **非 WorkBuddy 环境** 才允许降级到 HTTPS API (ima skills)。`scripts/ima_api.py` 通过 `WORKBUDDY_REQUIRE_CONNECTOR` 环境变量开关控制。

## 优先级链

```
┌─────────────────────────────────────────────────────┐
│ 检测 IMA_MCP_CALLBACK 环境变量                       │
│ (值 = Python 文件路径, 暴露 call_mcp(server, method, params)) │
│   ↓ 存在且能加载                                      │
│   → 用 MCPIMAClient 调 agent 注入的 MCP 工具         │
│   ★ WorkBuddy 默认首选                                │
├─────────────────────────────────────────────────────┤
│ 检测 IMA_CONNECTOR 环境变量                          │
│ (值 = connector 脚本路径)                             │
│   ↓ 存在且可执行                                      │
│   → 用 ConnectorIMAClient 调 connector 脚本         │
├─────────────────────────────────────────────────────┤
│ 检测 PATH 里的 `ima-connector` 命令                  │
│   ↓ 存在                                              │
│   → 用 ConnectorIMAClient 调命令                    │
├─────────────────────────────────────────────────────┤
│ 环境变量 WORKBUDDY_REQUIRE_CONNECTOR=1 时:            │
│   ↓ 没检测到上述任何 connector                          │
│   → 抛 RuntimeError 报错退出                          │
│   (禁止降级到 HTTPS, 强制要求先启用连接器)            │
├─────────────────────────────────────────────────────┤
│ 降级默认 (非 WorkBuddy 严格模式): 直连 HTTPS           │
│   → DirectIMAClient 用 ima-openapi-clientid/apikey headers │
└─────────────────────────────────────────────────────┘
```

## WorkBuddy 强制模式（重要）

**主人规则**: 不管怎么样, 在 WorkBuddy 内必须使用 IMA 连接器, 没有连接器才用 ima skills。

设置 `WORKBUDDY_REQUIRE_CONNECTOR=1` 后:

- ✅ 检测到 MCP/connector → 正常使用
- ❌ 没检测到 → 抛 `RuntimeError`, 脚本直接退出

错误信息示例:
```
❌ WorkBuddy 内必须使用 IMA 连接器, 但当前没检测到任何连接器。
请二选一:
  1) 启用 ima-mcp MCP 服务 + 设置 IMA_MCP_CALLBACK=<wrapper_path>
  2) 设置 IMA_CONNECTOR=<脚本路径> 或安装 ima-connector CLI
如在非 WorkBuddy 环境运行, 取消 WORKBUDDY_REQUIRE_CONNECTOR 即可降级到 HTTPS API。
```

不设这个变量 → 按"非严格模式"运行, 自动降级到 HTTPS。

## 模式 1: MCP 连接器（WorkBuddy 默认首选）

如果你的 Agent 暴露了 MCP 工具（如 WorkBuddy + ima-mcp MCP server），可以注入 callback。

**创建 callback 文件** `mcp_callback.py`:
```python
def call_mcp(server: str, method: str, params: dict) -> dict:
    """调用 MCP 工具 (agent 提供实现)"""
    # 通过文件队列或 HTTP 调 agent
    # (具体实现取决于 agent 怎么暴露 MCP 给子进程)
    ...
    return {...}
```

**设置环境变量**:
```bash
export IMA_MCP_CALLBACK="/path/to/mcp_callback.py"
export WORKBUDDY_REQUIRE_CONNECTOR=1    # WorkBuddy 内必设
python3 scripts/run_daily.sh
```

**Agent 端需要**:
- Agent 必须有 `mcp__ima-mcp__*` 工具可用
- Callback 文件中通过某种方式调 agent 的 MCP 工具 (文件队列/HTTP/stdin)

## 模式 2: Connector 脚本

如果你装了 IMA connector CLI 工具（叫 `ima-connector`），skill 会自动用。

**Connector 调用约定**:
```bash
ima-connector <api_path> <params_json>
# 返回 JSON 到 stdout
```

**手动指定 connector 路径**:
```bash
export IMA_CONNECTOR="/path/to/ima-connector"
export WORKBUDDY_REQUIRE_CONNECTOR=1    # WorkBuddy 内必设
python3 scripts/run_daily.sh
```

**API 路径格式**: 例如 `openapi/wiki/v1/search_knowledge_base`（不含 host 和 /）

## 模式 3: HTTPS API 降级（非 WorkBuddy 环境）

非 WorkBuddy 环境 + 没 connector 时自动降级。

**前提**: 有 IMA 凭证（`~/.config/ima/client_id` 和 `api_key`）

**优点**: 零依赖、跨平台、任何能跑 Python 的环境都能用

**用法**: 直接跑 `python3 scripts/ima_api.py` 即可

**重要**: WorkBuddy 内**禁止**用这个模式, 必须设 `WORKBUDDY_REQUIRE_CONNECTOR=1`。

## 自测

```bash
python3 scripts/ima_api.py
```

输出示例:
```
============================================================
IMA 客户端自测
============================================================
模式: mcp:/path/to/mcp_callback.py        ← MCP 连接器 (WorkBuddy 首选)
客户端类型: MCPIMAClient
✅ search_knowledge_base: 找到 2 条
最终模式: mcp:/path/to/mcp_callback.py
```

## 强制指定模式

如需在脚本里强制某种模式（不靠自动检测）:
```python
from ima_api import DirectIMAClient, ConnectorIMAClient, MCPIMAClient
import ima_api

# 强制直接 HTTPS (绕过 workbuddy_strict)
client = DirectIMAClient()

# 强制 connector
client = ConnectorIMAClient(["/path/to/ima-connector"])

# 强制 MCP
client = MCPIMAClient(call_mcp_fn=lambda s, m, p: {...})

# 替换全局
ima_api._client = client
ima_api._mode = "forced"
```

## 切换模式的成本

| 模式切换 | 成本 | 何时用 |
|---|---|---|
| HTTPS → connector | 低（改环境变量） | 想用 connector 的额外功能（缓存、批量、重试） |
| HTTPS → MCP | 中（需 agent 配合） | Agent 已经有 MCP 工具，零样板代码 |
| connector → MCP | 中 | Agent 升级到 MCP 后 |

## 故障排查

**Q: 报错 "WorkBuddy 内必须使用 IMA 连接器"**
A: 设了 `WORKBUDDY_REQUIRE_CONNECTOR=1` 但没 connector, 二选一:
   1. 取消 `WORKBUDDY_REQUIRE_CONNECTOR` (非 WorkBuddy 环境)
   2. 启用 ima-mcp + 设置 `IMA_MCP_CALLBACK`, 或安装 `ima-connector`

**Q: 一直走 HTTPS (direct)，但我想用 MCP**
A: 检查 `echo $IMA_MCP_CALLBACK` 是否设置, 且 callback 文件能正确 import

**Q: MCP 模式下 callback 加载失败**
A: 检查 callback 文件语法, `python3 /path/to/callback.py` 应能独立运行

**Q: HTTPS 模式 401 Unauthorized**
A: 凭证过期或不正确，去 https://ima.qq.com/agent-interface 重新生成
   (WorkBuddy 内禁用此模式, 必须切到 MCP/connector)

**Q: 凭证正确但 HTTPS 仍失败**
A: 检查 header 名, 必须是 `ima-openapi-clientid`/`ima-openapi-apikey` (不是 `X-IMA-*`)