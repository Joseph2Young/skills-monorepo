# Agent 兼容性矩阵

| Agent | skill 加载 | 定时调度 | 备注 |
|---|---|---|---|
| **Codex (官方)** | `~/.codex/skills/jq-daily-pipeline/` | 「已安排任务」面板 | 最佳支持 |
| **Claude Code** | `~/.claude/skills/jq-daily-pipeline/` 或项目级 | cron + slash command | 通过 `skill-installer` 装 |
| **Cursor** | 项目级 `.cursor/skills/` | IDE scheduler | 手动触发为主 |
| **Windsurf** | 项目级 `.windsurf/skills/` | 手动 / IDE | 类似 Cursor |
| **Continue.dev** | VS Code 扩展 | VS Code task | 需配置 |
| **GitHub Copilot Workspace** | repo `.github/skills/` | GitHub Actions | 用 Actions 调度 |
| **通用 CLI + cron/launchd** | `git clone` 到任意路径 | cron/launchd | 最通用 |
| **GitHub Actions** | repo 内 | `.github/workflows/` | 云端调度 |

## 安装方式

### Codex
```bash
# skill 已在 ~/.codex/skills/jq-daily-pipeline/，自动可用
# 如需更新: git -C ~/.codex/skills/jq-daily-pipeline pull
```

### Claude Code
```bash
# 1. 装到全局 skills 目录
mkdir -p ~/.claude/skills
cp -r jq-daily-pipeline ~/.claude/skills/

# 2. 或项目级
mkdir -p .claude/skills
cp -r jq-daily-pipeline .claude/skills/

# 3. 通过 skill-installer (推荐)
npx @anthropic-ai/skill-installer Joseph2Young/jq-daily-pipeline
```

### Cursor / Windsurf
```bash
# 项目级
mkdir -p .cursor/skills   # 或 .windsurf/skills
cp -r jq-daily-pipeline .cursor/skills/
```

### 通用 (任何 Python 环境)
```bash
git clone https://github.com/Joseph2Young/jq-daily-pipeline.git
cd jq-daily-pipeline
bash run_daily.sh
```

## 调度方式

### Codex 「已安排任务」面板
见 `agent_scheduled_task.md`

### macOS launchd
```bash
cat > ~/Library/LaunchAgents/com.user.jqdaily.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
    <key>Label</key><string>com.user.jqdaily</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/path/to/jq_daily_pipeline/run_daily.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
</dict>
</plist>
EOF
launchctl load ~/Library/LaunchAgents/com.user.jqdaily.plist
```

### Linux cron
```cron
0 9 * * * /bin/bash /path/to/jq_daily_pipeline/run_daily.sh >> /tmp/jq_cron.log 2>&1
```

### GitHub Actions
```yaml
# .github/workflows/jq-daily.yml
name: jq-daily
on:
  schedule:
    - cron: '0 1 * * *'  # UTC 01:00 = 北京 09:00
  workflow_dispatch:
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install requests
      - run: |
          mkdir -p ~/.config/ima
          echo "${{ secrets.IMA_CLIENT_ID }}" > ~/.config/ima/client_id
          echo "${{ secrets.IMA_API_KEY }}" > ~/.config/ima/api_key
          chmod 600 ~/.config/ima/*
          bash run_daily.sh
        env:
          IMA_KB_ID: ${{ secrets.IMA_KB_ID }}
          IMA_PARENT_FOLDER_ID: ${{ secrets.IMA_PARENT_FOLDER_ID }}
```

## Agent 注入 MCP callback 模板

如果你的 Agent 暴露了 MCP 工具，可以这样用模式 3:

### Claude Code
```python
# claude_mcp_callback.py
import anthropic
# 实际由 agent 注入
def call_mcp(server, method, params):
    # 通过 agent 的 MCP 接口调用
    return your_agent_mcp_client.call(server, method, params)
```

### Cursor
```python
# cursor_mcp_callback.py
def call_mcp(server, method, params):
    # Cursor 提供的 MCP 接口
    return cursor_mcp.call(server, method, params)
```

## 选择哪种调度方式？

| 场景 | 推荐方式 |
|---|---|
| 个人 Mac，Codex | Codex 「已安排任务」面板 |
| 个人 Mac，Claude Code | launchd + skill |
| Linux 服务器 | cron |
| 团队协作 | GitHub Actions |
| 想要云端高可用 | GitHub Actions |
| 完全本地 | launchd / cron |
