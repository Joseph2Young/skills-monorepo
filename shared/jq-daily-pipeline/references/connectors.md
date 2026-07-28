# IMA Connector 检测与降级

## 设计原则

**绝不依赖 MCP 或 ima-skill**。`scripts/ima_api.py` 实现 3 层降级策略，让 skill 跑在**任何**能跑 Python 的环境里。

## 优先级链

```
┌─────────────────────────────────────────────────────┐
│ 检测 IMA_CONNECTOR 环境变量                          │
│ (值 = connector 脚本路径)                             │
│   ↓ 存在且可执行                                      │
│   → 用 ConnectorIMAClient 调 connector 脚本         │
├─────────────────────────────────────────────────────┤
│ 检测 PATH 里的 `ima-connector` 命令                  │
│   ↓ 存在                                              │
│   → 用 ConnectorIMAClient 调命令                    │
├─────────────────────────────────────────────────────┤
│ 检测 IMA_MCP_CALLBACK 环境变量                       │
│ (值 = Python 文件路径, 暴露 call_mcp(server, method, params)) │
│   ↓ 存在                                              │
│   → 用 MCPIMAClient 调 agent 注入的 MCP 工具         │
├─────────────────────────────────────────────────────┤
│ 降级默认: 直连 HTTPS                                  │
│   → DirectIMAClient 用 X-IMA-CLIENTID/APIKEY headers │
└─────────────────────────────────────────────────────┘
```

## 模式 1: 直接 HTTPS（默认，无需配置）

**前提**: 有 IMA 凭证（`~/.config/ima/client_id` 和 `api_key`）

**优点**: 零依赖、跨平台、任何能跑 Python 的环境都能用

**用法**: 直接跑 `python3 scripts/ima_api.py` 即可

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
python3 scripts/run_daily.sh
```

**API 路径格式**: 例如 `openapi/wiki/v1/search_knowledge_base`（不含 host 和 /）

## 模式 3: MCP 注入

如果你的 Agent 暴露了 MCP 工具（如 Claude Code + IMA MCP server），可以注入 callback。

**创建 callback 文件** `mcp_callback.py`:
```python
def call_mcp(server: str, method: str, params: dict) -> dict:
    """调用 MCP 工具 (agent 提供实现)"""
    # 伪代码 - 实际由 agent 注入
    from anthropic_mcp import call_mcp_tool  # agent 提供的工具
    return call_mcp_tool(server, method, params)
```

**设置环境变量**:
```bash
export IMA_MCP_CALLBACK="/path/to/mcp_callback.py"
python3 scripts/run_daily.sh
```

**Agent 端需要**:
- Agent 必须有 `mcp` 工具可用
- Callback 文件中调用 agent 提供的 MCP 调用函数

## 自测

```bash
python3 scripts/ima_api.py
```

输出示例:
```
============================================================
IMA 客户端自测
============================================================
模式: direct                              ← 当前模式
凭证: OK
客户端类型: DirectIMAClient              ← 实际类
✅ search_knowledge_base: 找到 2 条
最终模式: direct
```

## 强制指定模式

如需在脚本里强制某种模式（不靠自动检测）:
```python
from ima_api import DirectIMAClient, ConnectorIMAClient, MCPIMAClient
import ima_api

# 强制直接 HTTPS
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
| direct → connector | 低（改环境变量） | 想用 connector 的额外功能（缓存、批量、重试） |
| direct → MCP | 中（需 agent 配合） | Agent 已经有 MCP 工具，零样板代码 |
| connector → MCP | 中 | Agent 升级到 MCP 后 |

## 故障排查

**Q: 一直走 direct，但我想用 connector**
A: 检查 `echo $IMA_CONNECTOR` 和 `which ima-connector`，确保至少一个存在

**Q: MCP 模式下报错 `IMA_MCP_CALLBACK not set`**
A: 设置环境变量指向你的 callback 文件

**Q: direct 模式 401 Unauthorized**
A: 凭证过期或不正确，去 https://ima.qq.com/agent-interface 重新生成
