#!/usr/bin/env python3
"""
Step 4d: 更新 pending 清单状态 (monitor 用)
"""
import json
from pathlib import Path

SHARPE_FILE = Path("/tmp/jq_real_sharpe.json")
PENDING_FILE = Path("/tmp/jq_pending.json")


def main():
    if not PENDING_FILE.exists():
        return
    if not SHARPE_FILE.exists():
        return

    sharpes = {x["sid"]: x for x in json.load(open(SHARPE_FILE))}
    data = json.load(open(PENDING_FILE))

    for p in data.get("pending", []):
        s = sharpes.get(p["sid"])
        if not s:
            continue
        p["sharpe"] = s.get("sharpe")
        p["backtest_id"] = s.get("backtest_id", p["backtest_id"])
        if s.get("sharpe") is not None:
            p["status"] = "done"

    PENDING_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    running = sum(1 for x in data["pending"] if x["status"] == "running")
    print(f"💾 更新 pending: {len(data['pending'])} 个 ({running} still running)")


if __name__ == "__main__":
    main()