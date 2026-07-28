#!/usr/bin/env python3
"""
Step 4c: 把"待完成回测"的策略写到 /tmp/jq_pending.json, 给 monitor_pipeline.sh 用
"""
import json
import subprocess
from pathlib import Path

SHARPE_FILE = Path("/tmp/jq_real_sharpe.json")
PENDING_FILE = Path("/tmp/jq_pending.json")


def main():
    if not SHARPE_FILE.exists():
        print(f"❌ 找不到 {SHARPE_FILE}")
        return
    sharpes = json.load(open(SHARPE_FILE))

    pending = []
    for r in sharpes:
        if r.get("skipped"):
            continue
        sid = r.get("strategy_id", "")
        title = r.get("title", "")
        sharpe = r.get("sharpe")
        bt_id = r.get("backtest_id", "")

        if sharpe is not None:
            status = "done"
        elif bt_id:
            status = "running"
        else:
            status = "todo"

        pending.append({
            "sid": r["sid"],
            "title": title,
            "strategy_id": sid,
            "backtest_id": bt_id,
            "sharpe": sharpe,
            "status": status,
        })

    PENDING_FILE.write_text(json.dumps({"pending": pending}, ensure_ascii=False, indent=2))
    running = sum(1 for x in pending if x["status"] == "running")
    done = sum(1 for x in pending if x["status"] == "done")
    print(f"💾 {PENDING_FILE}: {len(pending)} 个策略 ({running} running, {done} done)")


if __name__ == "__main__":
    main()