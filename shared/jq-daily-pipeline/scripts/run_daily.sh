#!/bin/bash
# 聚宽每日策略流水线 - 纯 jqcli 部分 (step 3, 4 launch, 5)
# 由 daily 9:00 automation 触发, 在 agent 任务窗口里跑
#
# 工作流 (agent 任务窗口完整流程):
#   1. agent 跑 step1_filter.py              (jqcli 拉候选)  ← 不在这个脚本里
#   2. agent 用 MCP get_knowledge_list 查重  ← 不在这个脚本里
#   3. agent 写 /tmp/jq_dedup_result.json    ← 不在这个脚本里
#   4. run_daily.sh 跑 step 3 克隆 + step 4 launch (非阻塞启动)
#   5. agent 用 run_in_background=true 跑 step4_poll.py + TaskOutput 轮询 1 小时
#   6. agent 重新跑 step5_review_build.py 生成 markdown
#   7. agent 用 MCP 上传 markdown            ← 不在这个脚本里
#
# 主人规则 (2026-07-28):
#   - 每天独立完整任务, 所有 step 跑完, 不跨天接续
#   - step 4 launch 后立即返回, 后续 polling 由 agent 用 TaskOutput 跑
#   - Sharpe 过滤条件: 0.8 < sharpe <= 3.0 (下限不带等号, 上限带等号)
#   - WorkBuddy 内不允许降级 HTTPS, step 2 和 step 6 必须 agent 用 MCP 完成
#
# ⚠️ WorkBuddy agent 必读:
#   - 2026-07-30: step6 上传 MCP 调 add_knowledge 必须串行, 不能并发
#     (IMA 服务端 per-folder 锁, 并发第二个会报 222000), 两次调用之间 sleep 0.5~1s
#   - 2026-07-30: step4_poll.py 加 sys.stdout.reconfigure(line_buffering=True), TaskOutput 可实时看输出
#   - 2026-07-31: 不在这里跑 step1, 避免 24h 窗口右移几秒导致 top3 post_id 漂移
#     agent 已经在 run_daily.sh 之前跑完 step1 + step2 写入 /tmp/jq_dedup_result.json

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JQS="${JQS:-/Users/ytf/Library/Python/3.9/bin/jqcli}"
export PATH="$(dirname $JQS):$PATH"

LOG="/tmp/jq_daily_$(date +%Y%m%d).log"
exec > "$LOG" 2>&1
echo "==== jq-daily-pipeline run_daily.sh start $(date) ===="
echo "注: step 1/2/6 由 agent 跑 (jqcli + MCP), 不在这个脚本里"
echo "注: step 4 launch 立即返回, agent 用 step4_poll.py + TaskOutput 轮询 1 小时"

# 检查 dedup_result.json (agent 在 run_daily.sh 之前已经跑完 step1 + step2 写入)
# 注: 不在这里重跑 step1_filter.py, 避免 24h 窗口右移几秒导致 top3 post_id 漂移
# (2026-07-31 修复, 见 SKILL.md 避雷点 #13)
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

# Step 4 launch: 非阻塞启动回测 (立即返回)
echo ""
echo "==== Step 4 launch: 非阻塞启动回测 ===="
python3 "$SCRIPT_DIR/step4_launch.py"

# 注: 不在这里阻塞等回测. agent 会用 run_in_background=true + TaskOutput 轮询 step4_poll.py (1 小时超时)
# 然后 agent 会重新跑 step5_review_build.py (根据 poll 后的 sharpe.json 生成 markdown)
# 然后 agent 用 MCP 上传 markdown

echo ""
echo "==== run_daily.sh 第一段完成 $(date) ===="
echo "下一步: agent 跑 step4_poll.py (run_in_background + TaskOutput 轮询 1 小时)"