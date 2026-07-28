#!/usr/bin/env python3
"""
Step 4 (launch): 非阻塞启动回测 (去 --wait), 立即返回
agent 跑完此脚本后, 用 run_in_background=true + TaskOutput 轮询回测完成状态
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

JQS = os.environ.get("JQS", "/Users/ytf/Library/Python/3.9/bin/jqcli")
DEDUP_FILE = Path("/tmp/jq_dedup_result.json")


def launch_backtest(strategy_id: str) -> str:
    """非阻塞启动回测, 立即返回. 返回 backtest_id (空 = 失败)"""
    if not strategy_id:
        return ""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    # 注意: 不带 --wait --wait-timeout, 启动后立即返回
    r = subprocess.run([
        JQS, "--format", "json", "backtest", "run", strategy_id,
        "--start", "2019-01-01", "--end", yesterday,
    ], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print(f"    ❌ 启动失败: {r.stderr.strip()}")
        return ""
    try:
        resp = json.loads(r.stdout)
    except Exception:
        print(f"    ⚠️ 启动响应解析失败: {r.stdout[:200]}")
        return ""
    return resp.get("id", resp.get("list_id", ""))


def main():
    if not DEDUP_FILE.exists():
        print(f"❌ 找不到 {DEDUP_FILE}")
        sys.exit(1)

    data = json.load(open(DEDUP_FILE))
    strategy_ids = data.get("strategy_ids", [])
    candidates = data.get("top3_after_dedup", [])

    bt_ids = []
    for i, sid in enumerate(strategy_ids, 1):
        title = candidates[i-1]["title"][:30] if i <= len(candidates) else ""
        print(f"s{i}: {title}")
        if not sid:
            bt_ids.append("")
            continue
        bt_id = launch_backtest(sid)
        bt_ids.append(bt_id)
        if bt_id:
            print(f"    ✅ 启动 backtest_id={bt_id[:20]}... (后台跑, 不阻塞)")
        else:
            print(f"    ⚠️ 启动失败 (跳过此策略)")

    # 写 backtest_ids 到 dedup_result.json 给 step4_poll.py 用
    data["backtest_ids"] = bt_ids
    DEDUP_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    started = sum(1 for b in bt_ids if b)
    print(f"\n💾 {DEDUP_FILE}: {started} 个 backtest 已启动 (后台跑)")
    print(f"💡 下一步: 跑 step4_poll.py 轮询 Sharpe (超时 1 小时)")


if __name__ == "__main__":
    main()