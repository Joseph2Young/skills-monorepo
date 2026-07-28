#!/usr/bin/env python3
"""
Step 4: 跑 2019-01-01 ~ T-1 回测 + 取 Sharpe
"""
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

JQS = os.environ.get("JQS", "/Users/ytf/Library/Python/3.9/bin/jqcli")
DEDUP_FILE = Path("/tmp/jq_dedup_result.json")
SHARPE_FILE = Path("/tmp/jq_real_sharpe.json")
CODES_DIR = Path("/tmp/jq_codes")


def compute_sharpe_from_timeseries(bt_id: str) -> float:
    """回测 stats 没有 Sharpe 时, 从 time series 计算"""
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


def get_sharpe(strategy_id: str) -> tuple:
    """拿指定 strategy 最新 backtest 的 (bt_id, sharpe)"""
    if not strategy_id:
        return "", None
    
    # 取最新 backtest ID
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
    
    # 优先用 stats 的 Sharpe
    r = subprocess.run([JQS, "--format", "json", "backtest", "show", bt_id],
                       capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
    except:
        return bt_id, None
    metrics = d.get("metrics", {})
    sharpe = metrics.get("sharpe")
    if sharpe is None:
        sharpe = compute_sharpe_from_timeseries(bt_id)
    return bt_id, sharpe


def main():
    if not DEDUP_FILE.exists():
        print(f"❌ 找不到 {DEDUP_FILE}")
        sys.exit(1)
    
    data = json.load(open(DEDUP_FILE))
    strategy_ids = data.get("strategy_ids", [])
    candidates = data.get("top3_after_dedup", [])
    
    # 昨天日期 (T-1)
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    results = []
    for i, sid in enumerate(strategy_ids, 1):
        if not sid:
            results.append({"sid": f"s{i}", "strategy_id": "", "backtest_id": "", "sharpe": None, "skipped": True})
            continue
        
        print(f"  s{i}: 检查 {sid}...")
        # 拿最新 backtest (如果之前跑过)
        bt_id, sharpe = get_sharpe(sid)
        
        if sharpe is not None:
            print(f"    已有 backtest {bt_id[:12]}, Sharpe={sharpe}")
        else:
            # 启动新回测
            print(f"    启动新回测 (2019-01-01 ~ {yesterday})...")
            r = subprocess.run([
                JQS, "--format", "json", "backtest", "run", sid,
                "--start", "2019-01-01", "--end", yesterday,
                "--wait", "--wait-timeout", "14400", "--poll-interval", "60"
            ], capture_output=True, text=True)
            
            try:
                resp = json.loads(r.stdout)
            except:
                resp = {}
            bt_id = resp.get("id", resp.get("list_id", ""))
            if not bt_id:
                # 用 list 取最新
                bt_id, sharpe = get_sharpe(sid)
            else:
                # 取 stats
                r = subprocess.run([JQS, "--format", "json", "backtest", "show", bt_id],
                                  capture_output=True, text=True)
                try:
                    d = json.loads(r.stdout)
                    sharpe = d.get("metrics", {}).get("sharpe")
                except:
                    sharpe = None
                if sharpe is None:
                    sharpe = compute_sharpe_from_timeseries(bt_id)
        
        results.append({
            "sid": f"s{i}",
            "strategy_id": sid,
            "backtest_id": bt_id,
            "sharpe": sharpe,
            "skipped": False,
        })
        if sharpe is not None:
            print(f"    ✅ Sharpe={sharpe:.4f}")
        else:
            print(f"    ❌ 无法获取 Sharpe")
    
    SHARPE_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n💾 {SHARPE_FILE}")


if __name__ == "__main__":
    main()
