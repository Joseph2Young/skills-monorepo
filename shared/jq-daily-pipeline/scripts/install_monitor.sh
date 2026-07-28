#!/bin/bash
# 安装 jq-daily-pipeline monitor daemon 到 launchd
# 每 5 分钟跑一次 monitor_pipeline.sh

set -e
PLIST_NAME="com.workbuddy.jq-daily-monitor"
PLIST_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/${PLIST_NAME}.plist"
PLIST_DST="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

# 卸载旧的 (如有)
if launchctl list | grep -q "$PLIST_NAME"; then
  launchctl unload "$PLIST_DST" 2>/dev/null || true
fi

# 复制 plist
mkdir -p "$HOME/Library/LaunchAgents"
cp "$PLIST_SRC" "$PLIST_DST"

# 加载
launchctl load "$PLIST_DST"

# 验证
if launchctl list | grep -q "$PLIST_NAME"; then
  echo "✅ 安装成功, daemon 已启动"
  echo ""
  echo "查看状态:"
  echo "  launchctl list | grep $PLIST_NAME"
  echo ""
  echo "查看日志:"
  echo "  tail -f /tmp/jq_monitor_\$(date +%Y%m%d).log"
  echo ""
  echo "卸载:"
  echo "  launchctl unload $PLIST_DST"
else
  echo "❌ 安装失败"
  exit 1
fi