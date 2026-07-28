#!/bin/bash
# 聚宽每日策略流水线 - 纯 jqcli 部分 (step 1, 3, 4, 5)
# 由 daily 9:00 automation 触发, 在 agent 任务窗口里跑
#
# 工作流 (agent 任务窗口完整流程):
#   1. agent 跑 step1_filter.py             (jqcli 拉候选)
#   2. agent 用 MCP get_knowledge_list 查重  ← 不在这个脚本里
#   3. agent 写 /tmp/jq_dedup_result.json    ← 不在这个脚本里
#   4. run_daily.sh 跑 step 3 克隆 + step 4 回测阻塞 + step 5 生成 markdown
#   5. agent 用 MCP 上传 markdown            ← 不在这个脚本里
#
# 主人规则 (2026-07-28): 每天独立完整任务, 所有 step 跑完, 不跨天接续.
# WorkBuddy 内不允许降级 HTTPS, step 2 和 step 6 必须 agent 用 MCP 完成.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JQS="${JQS:-/Users/ytf/Library/Python/3.9/bin/jqcli}"
export PATH="$(dirname $JQS):$PATH"

LOG="/tmp/jq_daily_$(date +%Y%m%d).log"
exec > "$LOG" 2>&1
echo "==== jq-daily-pipeline run_daily.sh start $(date) ===="
echo "注: step 2 (IMA 查重) 和 step 6 (IMA 上传) 由 agent 用 MCP 完成, 不在这个脚本里"

# Step 1: 拉候选
echo ""
echo "==== Step 1: 拉候选 + 24h 窗口 + 去重 ===="
python3 "$SCRIPT_DIR/step1_filter.py"

# 检查 dedup_result.json (agent 已经生成)
REMAINING=$(python3 -c "
import json
try:
    d = json.load(open('/tmp/jq_dedup_result.json'))
    print(len(d.get('top3_after_dedup', [])))
except: print(0)
")
if [ "$REMAINING" = "0" ]; then
  echo "⚠️ 没有新策略需要入库, 全部被查重"
  exit 0
fi

# Step 3: 克隆
echo ""
echo "==== Step 3: 克隆 + 拉代码 ===="
python3 "$SCRIPT_DIR/step3_clone.py"

# Step 4: 启动回测 + 阻塞等完成 (1-5 小时)
echo ""
echo "==== Step 4: 启动回测 + 阻塞等完成 (1-5 小时) ===="
python3 "$SCRIPT_DIR/step4_backtest.py"

# Step 5: AI 审查 + 生成 markdown
echo ""
echo "==== Step 5: AI 审查 + 生成 markdown ===="
python3 "$SCRIPT_DIR/step5_review_build.py"

echo ""
echo "==== run_daily.sh 完成 $(date), 等 agent 用 MCP 上传 ===="
echo "见 /tmp/jq_uploads/*.md"