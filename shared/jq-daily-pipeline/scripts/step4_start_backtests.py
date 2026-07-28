#!/usr/bin/env python3
"""
Step 4a: 启动新回测 (非阻塞, 不重复启动已有)
仅在没有 backtest 时启动; 已有 backtest (不管是否完成) 跳过
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

JQS = os.environ.get("JQS", "/Users/ytf/Library/Python/3.9/bin/jqcli")
DEDUP_FILE = Path("/tmp/jq_dedup_result.json")


def has_any_backtest(strategy_id: str) -> bool:
    """检查策略是否已有任何 backtest (不管是否完成)"""
    if not strategy_id:
        return False
    r = subprocess.run([JQS, "--format", "json", "backtest", "ls", strategy_id, "--all", "--limit", "1"],
                       capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
    except:
        return False
    return bool(d.get("items"))


def start_backtest(strategy_id: str) -> str:
    """非阻塞启动回测, 立即返回"""
    if not strategy_id:
        return ""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    # 不带 --wait, 启动后立即返回
    r = subprocess.run([
        JQS, "--format", "json", "backtest", "run", strategy_id,
        "--start", "2019-01-01", "--end", yesterday,
    ], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print(f"    ❌ 启动失败: {r.stderr.strip()}")
        return ""
    try:
        resp = json.loads(r.stdout)
    except:
        print(f"    ⚠️ 启动响应解析失败: {r.stdout[:200]}")
        return ""
    bt_id = resp.get("id", resp.get("list_id", ""))
    print(f"    ✅ 启动 backtest_id={bt_id[:20] if bt_id else '(none)'} (后台跑, 不阻塞)")
    return bt_id


def main():
    if not DEDUP_FILE.exists():
        print(f"❌ 找不到 {DEDUP_FILE}")
        sys.exit(1)

    data = json.load(open(DEDUP_FILE))
    strategy_ids = data.get("strategy_ids", [])

    for i, sid in enumerate(strategy_ids, 1):
        title = data.get("top3_after_dedup", [{}])[i-1].get("title", f"s{i}")[:30]
        print(f"s{i}: {title}")
        if not sid:
            print(f"    ⊘ 跳过 (strategy_id 为空)")
            continue
        if has_any_backtest(sid):
            print(f"    ⊘ 已有 backtest, 跳过启动")
            continue
        start_backtest(sid)

    print("\n💡 回测在后台跑, 不阻塞. 完成后下次任务窗口会自动检测.")


if __name__ == "__main__":
    main()