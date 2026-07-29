# 各 Agent 的定时任务配置

## Codex「已安排任务」面板

| 字段 | 填什么 |
|---|---|
| 任务名称 | `聚宽每日策略扫描` |
| 触发时间 | **每天 09:00** |
| 时区 | Asia/Shanghai |

**提示词**:
```
执行 jq-daily-pipeline skill：每天 9 点扫描过去 24 小时聚宽新发布的最热门 Top 3 策略，
跑 7.5 年（2019-01-01 ~ 昨日）回测，0.8 < Sharpe <= 3.0 通过后按聚宽策略审查分类提示词 v1.0
分类（12 大类），按 {年份}_{T编号}_{T简称}_{作者}_{标题核心}_s{Sharpe.2f}.md 命名后上传到 IMA 知识库。
跑 run_daily.sh 即可（位置参考 SKILL.md）。
```

## Claude Code

### 方案 A: 用 slash command + cron

创建 `~/.claude/commands/jq-daily.md`:
```markdown
# jq-daily
执行聚宽每日策略扫描:
1. 加载 jq-daily-pipeline skill
2. 跑 run_daily.sh
3. 汇报：扫描了多久 / Top 3 / 几个通过查重 / 几个跑回测 / 几个 0.8 < Sharpe <= 3.0 通过 / 几个最终入库
4. 失败的策略说明原因
```

加 cron（macOS）:
```cron
0 9 * * * /usr/local/bin/claude /invoke jq-daily >> /tmp/jq_claude.log 2>&1
```

### 方案 B: GitHub Actions 远程触发

见 `agent_compatibility.md` 的 GitHub Actions 配置。

## Cursor / Windsurf

不支持内置调度。建议：
- 手动触发：在 chat 里说"**跑 jq-daily-pipeline**"
- 或用 GitHub Actions 远程调度，结果通过 webhook 推回 IDE

## macOS launchd (通用 CLI)

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
    <key>StandardOutPath</key><string>/tmp/jq_stdout.log</string>
    <key>StandardErrorPath</key><string>/tmp/jq_stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key><string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF
launchctl load ~/Library/LaunchAgents/com.user.jqdaily.plist
```

## Linux cron

```cron
0 9 * * * /bin/bash /path/to/jq_daily_pipeline/run_daily.sh >> /tmp/jq_cron.log 2>&1
```

## GitHub Actions (云端)

```yaml
# .github/workflows/jq-daily.yml
name: jq-daily-pipeline
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
        with: { python-version: '3.11' }
      - run: pip install requests
      - name: 配置 IMA 凭证
        run: |
          mkdir -p ~/.config/ima
          echo "${{ secrets.IMA_CLIENT_ID }}" > ~/.config/ima/client_id
          echo "${{ secrets.IMA_API_KEY }}" > ~/.config/ima/api_key
          chmod 600 ~/.config/ima/*
      - name: 跑流水线
        env:
          IMA_KB_ID: ${{ secrets.IMA_KB_ID }}
          IMA_PARENT_FOLDER_ID: ${{ secrets.IMA_PARENT_FOLDER_ID }}
          JQCLI_TOKEN: ${{ secrets.JQCLI_TOKEN }}
        run: bash run_daily.sh
```

需要的 Secrets (在 GitHub repo Settings → Secrets 配置):
- `IMA_CLIENT_ID` / `IMA_API_KEY` / `IMA_KB_ID` / `IMA_PARENT_FOLDER_ID`
- `JQCLI_TOKEN` (聚宽的 cookie 或 token)

## 取消任务

| Agent | 操作 |
|---|---|
| Codex | 面板里删除任务 |
| Claude Code | `crontab -e` 删行 |
| macOS launchd | `launchctl unload ~/Library/LaunchAgents/com.user.jqdaily.plist` |
| Linux cron | `crontab -e` 删行 |
| GitHub Actions | 删 `.github/workflows/jq-daily.yml` 或 disable workflow |
