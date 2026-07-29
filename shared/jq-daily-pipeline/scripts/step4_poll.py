#!/usr/bin/env python3
"""
Step 4 (poll): 轮询回测完成状态, 超时 1 小时 (3600s) 强制终止

用法:
  python3 step4_poll.py [--timeout 3600] [--interval 60]

行为:
- 每 interval 秒检查一次 strategy 的 backtest metrics.sharpe
- 所有 strategy 都完成 → 立即返回
- 超时 (timeout 秒) 后强制退出, 已完成的写 sharpe, 未完成的标记 timeout
- agent 用 run_in_background=true 启动本脚本, TaskOutput 轮询
"""
import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

JQS = os.environ.get("JQS", "/Users/ytf/Library/Python/3.9/bin/jqcli")
DEDUP_FILE = Path("/tmp/jq_dedup_result.json")
SHARPE_FILE = Path("/tmp/jq_real_sharpe.json")


def compute_sharpe_from_timeseries(bt_id: str) -> float:
    """从 time series 计算 Sharpe (备用, stats 没有时)"""
    r = subprocess.run([JQS, "--format", "json", "backtest", "result", bt_id],
                       capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
    except:
        return None
    r_data = d.get("data", {}).get("result", {})
    overall = r_data.get("overallReturn", {})
    times = overall.get("time", [])
    values = overall.get("value", [])
    if len(times) < 30:
        return None
    rets = [(values[i] - values[i-1]) / 100 for i in range(1, len(values))]
    mean = sum(rets) / len(rets)
    var = sum((x - mean) ** 2 for x in rets) / len(rets)
    std = math.sqrt(var) if var > 0 else 0
    return (mean / std) * math.sqrt(252) if std > 0 else 0


def check_sharpe(bt_id: str):
    """检查单个 backtest 的 Sharpe. 返回 (status, sharpe)
    status: 'done' | 'running' | 'notfound' | 'error'
    """
    if not bt_id:
        return "notfound", None
    r = subprocess.run([JQS, "--format", "json", "backtest", "show", bt_id],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        return "error", None
    try:
        d = json.loads(r.stdout)
    except:
        return "error", None

    # running 状态直接返回 (jqcli running 时 metrics 通常是空 list)
    status_str = (d.get("status") or "").lower()
    if status_str == "running":
        return "running", None

    metrics = d.get("metrics")
    # running 中 metrics 通常是 list / 空 dict; 都按未完成处理
    if not isinstance(metrics, dict):
        return "running", None

    sharpe = metrics.get("sharpe")
    if sharpe is not None:
        return "done", sharpe
    # 有 metrics 但无 sharpe 字段 → 还在算 → 视为 running
    return "running", None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=3600, help="超时秒数 (默认 3600 = 1 小时)")
    parser.add_argument("--interval", type=int, default=60, help="轮询间隔秒数 (默认 60)")
    args = parser.parse_args()

    if not DEDUP_FILE.exists():
        print(f"❌ 找不到 {DEDUP_FILE}")
        sys.exit(1)

    data = json.load(open(DEDUP_FILE))
    strategy_ids = data.get("strategy_ids", [])
    backtest_ids = data.get("backtest_ids", [])
    candidates = data.get("top3_after_dedup", [])

    if not backtest_ids:
        # 兼容: 如果没有 backtest_ids, 退化为查 strategy 最新 backtest
        print("⚠️ 无 backtest_ids, 用 strategy_id 查最新 backtest")
        backtest_ids = [""] * len(strategy_ids)

    n = len(strategy_ids)
    if n == 0:
        print("⚠️ 无策略")
        return

    print(f"==== Step 4 poll: {n} 个策略, 超时 {args.timeout}s, 间隔 {args.interval}s ====")
    deadline = time.time() + args.timeout
    results = [None] * n  # 每项 {"status": ..., "sharpe": ..., "bt_id": ...}

    while True:
        pending = 0
        for i in range(n):
            if results[i] and results[i].get("status") == "done":
                continue
            if results[i] and results[i].get("status") == "notfound":
                continue
            sid = strategy_ids[i] if i < len(strategy_ids) else ""
            bt_id = backtest_ids[i] if i < len(backtest_ids) else ""
            title = candidates[i]["title"][:30] if i < len(candidates) else ""
            status, sharpe = check_sharpe(bt_id) if bt_id else check_sharpe_via_strategy(sid)
            results[i] = {"sid": f"s{i+1}", "strategy_id": sid, "backtest_id": bt_id, "sharpe": sharpe, "status": status}
            elapsed = int(args.timeout - (deadline - time.time()))
            if status == "done":
                print(f"  ✅ [{elapsed}s] {title[:20]} Sharpe={sharpe:.4f}")
            elif status == "running":
                pending += 1
            else:
                results[i]["status"] = "error"

        if pending == 0:
            print(f"\n💾 全部完成, 退出轮询")
            break
        if time.time() >= deadline:
            print(f"\n⏰ 超时 {args.timeout}s, 仍有 {pending} 个未完成")
            for r in results:
                if r and r.get("status") == "running":
                    r["status"] = "timeout"
                    r["sharpe"] = None
            break

        time.sleep(args.interval)

    SHARPE_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n💾 {SHARPE_FILE}")
    done = sum(1 for r in results if r and r.get("status") == "done")
    timeout_n = sum(1 for r in results if r and r.get("status") == "timeout")
    print(f"汇总: done={done}, timeout={timeout_n}")


def check_sharpe_via_strategy(strategy_id: str):
    """无 bt_id 时, 通过 strategy_id 查最新 backtest 的 Sharpe"""
    if not strategy_id:
        return "notfound", None
    r = subprocess.run([JQS, "--format", "json", "backtest", "ls", strategy_id, "--all", "--limit", "1"],
                       capture_output=True, text=True, timeout=30)
    try:
        d = json.loads(r.stdout)
    except:
        return "error", None
    items = d.get("items", [])
    if not items:
        return "notfound", None
    bt_id = items[0].get("id", "")
    if not bt_id:
        return "notfound", None
    return check_sharpe(bt_id)


if __name__ == "__main__":
    main()