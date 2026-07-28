#!/bin/bash
# 聚宽每日策略扫描 → IMA 入库 主入口
# 由 Codex agent 内的定时任务每天 09:00 触发

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JQS="/Users/ytf/Library/Python/3.9/bin/jqcli"  # 改成你电脑上的实际路径
export PATH="$(dirname $JQS):$PATH"
LOG="/tmp/jq_daily_$(date +%Y%m%d).log"

mkdir -p /tmp/jq_codes /tmp/jq_uploads
exec > "$LOG" 2>&1
echo "==== jq-daily-pipeline start $(date) ===="

# Step 1
echo ""
echo "==== Step 1: 拉候选 + 24h 窗口 + 去重 ===="
python3 "$SCRIPT_DIR/step1_filter.py"

# Step 2
echo ""
echo "==== Step 2: IMA 年度查重 ===="
python3 "$SCRIPT_DIR/step2_ima_dedup.py"

# 检查是否还有候选
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

# Step 3
echo ""
echo "==== Step 3: 克隆 + 拉代码 ===="
python3 "$SCRIPT_DIR/step3_clone.py"

# Step 4
echo ""
echo "==== Step 4: 跑回测 + 取 Sharpe ===="
python3 "$SCRIPT_DIR/step4_backtest.py"

# Step 5
echo ""
echo "==== Step 5: AI 审查 + 生成 markdown ===="
python3 "$SCRIPT_DIR/step5_review_build.py"

# Step 6
echo ""
echo "==== Step 6: 上传 IMA ===="
python3 "$SCRIPT_DIR/step6_upload.py"

echo ""
echo "==== 全部完成 $(date) ===="
