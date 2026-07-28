#!/bin/bash
# 聚宽每日策略流水线 - 启动段
# 跑 Step 1-4 (拉候选 → 查重 → 克隆 → 启动回测) → 写待监控清单 → 退出
# 由 daily 9:00 automation 触发
#
# 启动后回测可能跑 1-5 小时, monitor_pipeline.sh 会持续监听完成状态

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JQS="${JQS:-/Users/ytf/Library/Python/3.9/bin/jqcli}"
export PATH="$(dirname $JQS):$PATH"

if [ "${IMA_ALLOW_HTTPS:-0}" != "1" ]; then
  export WORKBUDDY_REQUIRE_CONNECTOR=1
fi

LOG="/tmp/jq_start_$(date +%Y%m%d).log"
exec > "$LOG" 2>&1
echo "==== jq-daily-pipeline START $(date) ===="
echo "WorkBuddy 严格模式: WORKBUDDY_REQUIRE_CONNECTOR=${WORKBUDDY_REQUIRE_CONNECTOR:-0}"

# Step 1: 拉候选 + 24h 窗口 + 去重
echo ""
echo "==== Step 1: 拉候选 + 24h 窗口 + 去重 ===="
python3 "$SCRIPT_DIR/step1_filter.py"

# Step 2: IMA 年度查重
echo ""
echo "==== Step 2: IMA 年度查重 ===="
python3 "$SCRIPT_DIR/step2_ima_dedup.py"

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

# Step 4a: 启动新回测 (后台)
echo ""
echo "==== Step 4a: 启动新回测 (后台) ===="
python3 "$SCRIPT_DIR/step4_start_backtests.py"

# Step 4b: 立即检查已有 Sharpe (避免重复启动)
echo ""
echo "==== Step 4b: 检查已有 backtest ===="
python3 "$SCRIPT_DIR/step4_backtest.py"

# 写待监控清单
echo ""
echo "==== 写待监控清单 /tmp/jq_pending.json ===="
python3 "$SCRIPT_DIR/step4_write_pending.py"

echo ""
echo "==== START 完成 $(date) ===="
echo "monitor_pipeline.sh 会持续监听 /tmp/jq_pending.json 中的策略"