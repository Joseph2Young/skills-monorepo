#!/bin/bash
# 聚宽每日策略流水线 - 持续监听
# 由 launchd 每 5 分钟触发一次
#
# 检查 /tmp/jq_pending.json 中的待完成策略:
#   - 有 Sharpe (≥1.0) → 生成 markdown + 触发 MCP 上传
#   - 仍在跑 → 等下次
#   - Sharpe < 1.0 → 标记 skip
# 全部处理完后清空 /tmp/jq_pending.json

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JQS="${JQS:-/Users/ytf/Library/Python/3.9/bin/jqcli}"
export PATH="$(dirname $JQS):$PATH"

if [ "${IMA_ALLOW_HTTPS:-0}" != "1" ]; then
  export WORKBUDDY_REQUIRE_CONNECTOR=1
fi

LOG="/tmp/jq_monitor_$(date +%Y%m%d).log"
exec >> "$LOG" 2>&1
echo ""
echo "==== monitor check $(date) ===="

if [ ! -f /tmp/jq_pending.json ]; then
  echo "无待监控清单, 跳过"
  exit 0
fi

PENDING_COUNT=$(python3 -c "
import json
d = json.load(open('/tmp/jq_pending.json'))
print(len([x for x in d.get('pending', []) if x.get('status') == 'running']))
" 2>/dev/null || echo 0)

if [ "$PENDING_COUNT" = "0" ]; then
  echo "全部完成, 跳过"
  exit 0
fi

# 检查回测状态
echo "检查 $PENDING_COUNT 个待完成策略..."
python3 "$SCRIPT_DIR/step4_backtest.py"

# 生成 markdown (Sharpe ≥ 1.0)
echo ""
echo "==== 生成 markdown ===="
python3 "$SCRIPT_DIR/step5_review_build.py"

# 标记"待上传"策略
echo ""
echo "==== 标记待上传清单 /tmp/jq_upload_trigger.json ===="
python3 "$SCRIPT_DIR/step6_write_upload_trigger.py"

# 触发 agent 处理 (通过 trigger 文件 + automation)
# agent 端 automation 检测 trigger 文件后用 MCP 上传
UPLOAD_COUNT=$(python3 -c "
import json
try:
    d = json.load(open('/tmp/jq_upload_trigger.json'))
    print(len(d.get('to_upload', [])))
except: print(0)
" 2>/dev/null || echo 0)

if [ "$UPLOAD_COUNT" -gt "0" ]; then
  echo "📤 $UPLOAD_COUNT 个策略待上传, 触发 agent 处理..."
  # 写 trigger 信号, agent automation 检测到后会用 MCP 上传
  date +%s > /tmp/jq_upload_signal
fi

# 更新 pending 状态
python3 "$SCRIPT_DIR/step4_update_pending.py"

REMAINING=$(python3 -c "
import json
try:
    d = json.load(open('/tmp/jq_pending.json'))
    print(len([x for x in d.get('pending', []) if x.get('status') == 'running']))
except: print(0)
" 2>/dev/null || echo 0)

if [ "$REMAINING" = "0" ]; then
  echo "✅ 全部完成, 清理 pending"
  rm -f /tmp/jq_pending.json
  # 推送通知 (微信)
  if [ -n "${WECHAT_WEBHOOK:-}" ]; then
    curl -s -X POST "$WECHAT_WEBHOOK" \
      -H 'Content-Type: application/json' \
      -d "{\"msgtype\":\"markdown\",\"markdown\":{\"content\":\"# 聚宽策略入库完成\n$UPLOAD_COUNT 个策略已上传 IMA, 见 /tmp/jq_uploads/\"}}"
  fi
fi