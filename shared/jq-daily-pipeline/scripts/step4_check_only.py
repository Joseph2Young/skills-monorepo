#!/usr/bin/env python3
"""
Step 4 (monitor 模式): 只检查已有 backtest, 不启动新的
"""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

JQS = os.environ.get("JQS", "/Users/ytf/Library/Python/3.9/bin/jqcli")
DEDUP_FILE = Path("/tmp/jq_dedup_result.json")
SHARPE_FILE = Path("/tmp/jq_real_sharpe.json")


def get_sharpe_only(strategy_id: str) -> tuple:
    """只检查已有 backtest, 没就返回 ('', None)"""
    if not strategy_id:
        return "", None

    r = subprocess.run([JQS, "--format", "json", "backtest", "ls", strategy_id, "--all", "--limit", "1"],
                       capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
    except:
        return "", None
    items = d.get("items", [])
    if not items:
        return "", None
    bt_id = items[0].get("id", "")
    if not bt_id:
        return "", None

    r = subprocess.run([JQS, "--format", "json", "backtest", "show", bt_id],
                       capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
    except:
        return bt_id, None
    metrics = d.get("metrics", {})
    return bt_id, metrics.get("sharpe")


def main():
    if not DEDUP_FILE.exists():
        print(f"❌ 找不到 {DEDUP_FILE}")
        sys.exit(1)

    data = json.load(open(DEDUP_FILE))
    strategy_ids = data.get("strategy_ids", [])
    candidates = data.get("top3_after_dedup", [])

    results = []
    for i, sid in enumerate(strategy_ids, 1):
        title = candidates[i-1]["title"][:30] if i <= len(candidates) else ""
        if not sid:
            results.append({"sid": f"s{i}", "title": title, "strategy_id": "", "backtest_id": "", "sharpe": None, "skipped": True})
            continue

        bt_id, sharpe = get_sharpe_only(sid)
        if sharpe is not None:
            print(f"  ✅ {title[:20]} Sharpe={sharpe:.4f}")
        else:
            print(f"  ⏳ {title[:20]} 仍在跑 (bt_id={bt_id[:12] if bt_id else '(none)'})")

        results.append({
            "sid": f"s{i}",
            "title": title,
            "strategy_id": sid,
            "backtest_id": bt_id,
            "sharpe": sharpe,
            "skipped": False,
        })

    SHARPE_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n💾 {SHARPE_FILE}")


if __name__ == "__main__":
    main()