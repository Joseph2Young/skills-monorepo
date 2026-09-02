#!/usr/bin/env python3
"""本地回测 CLI：mom（动量轮动）/ zcph（组合再平衡）。

用法见 SKILL.md。数据 CSV 需含 date,open,high,low,close,volume 列。"""
import json
import os

import pandas as pd


def load_csv(spec: str):
    code, path = spec.split(":", 1)
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    if "preClose" not in df.columns:
        df["preClose"] = df["close"].shift(1)
        df["zdf"] = df["close"].pct_change() * 100
    return code, df[["date", "open", "high", "low", "close", "volume", "preClose", "zdf"]]


def dump_metrics(m: dict, outdir: str) -> None:
    os.makedirs(outdir, exist_ok=True)
    keys = ["start_date", "end_date", "total_cash", "final_value", "total_return",
            "annual_return", "max_drawdown", "max_drawdown_date", "sharpe_ratio",
            "win_rate", "total_commission", "excess_return_pct"]
    summary = {k: m.get(k) for k in keys if k in m}
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    with open(os.path.join(outdir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)


def run_mom(a) -> None:
    from xg_mom_backtrader.xg_mom_backtrader import xg_mom_backtrader
    bt = xg_mom_backtrader(
        start_date=a.start, end_date=a.end,
        stock_list=[s.split(":", 1)[0] for s in a.data],
        index_stock=a.index, cash=a.cash, comm=a.comm,
        mom_type="百分比", mom_value=1.0, mom_daily=a.mom_daily,
        min_mom=0.0, max_mom=5.0, buy_rank=a.buy_rank,
        sell_zdf=a.sell_zdf, sell_amount=a.cash, max_workers=4)
    for spec in a.data:
        code, df = load_csv(spec)
        bt.add_stock_data_from_dataframe(code, df)
    bt.run_backtest()
    dump_metrics(bt.get_performance_metrics(), a.outdir)


def run_zcph(a) -> None:
    from xg_zcph_backtrader.xg_zcph_backtrader import xg_zcph_backtrader
    codes = [s.split(":", 1)[0] for s in a.data]
    # 单值自动广播到标的数量（引擎要求列表长度与 stock_list 一致）
    weights = (a.weights * len(codes)) if len(a.weights) == 1 else a.weights
    deviation = (a.deviation * len(codes)) if len(a.deviation) == 1 else a.deviation
    if len(weights) != len(codes) or len(deviation) != len(codes):
        raise SystemExit(f"weights/deviation 数量({len(weights)}/{len(deviation)})须为 1 或等于标的数({len(codes)})")
    bt = xg_zcph_backtrader(
        start_date=a.start, end_date=a.end, stock_list=codes,
        dt_type="百分比", weight_list=weights, deviation_list=deviation,
        interval=a.interval, index_stock=a.index, cash=a.cash,
        sell_zdf=a.sell_zdf, buy_zdf=a.buy_zdf, trade_value=a.trade_value,
        comm=a.comm, max_workers=4, use_custom_data=True)
    for spec in a.data:
        code, df = load_csv(spec)
        bt.add_stock_data_from_dataframe(code, df)
    bt.run_backtest()
    dump_metrics(bt.get_performance_metrics(), a.outdir)


def build_parser():
    ap = __import__("argparse").ArgumentParser()
    sub = ap.add_subparsers(dest="engine", required=True)

    pm = sub.add_parser("mom", help="动量轮动")
    pm.add_argument("--mom-daily", type=int, default=25)
    pm.add_argument("--buy-rank", type=int, default=1)
    pm.add_argument("--sell-zdf", type=float, default=0.03)

    pz = sub.add_parser("zcph", help="组合再平衡")
    pz.add_argument("--weights", type=float, nargs="+", default=[0.35, 0.35, 0.30])
    pz.add_argument("--deviation", type=float, nargs="+", default=[0.10, 0.10, 0.05])
    pz.add_argument("--interval", type=int, default=20)
    pz.add_argument("--sell-zdf", type=float, default=0.03)
    pz.add_argument("--buy-zdf", type=float, default=-0.03)
    pz.add_argument("--trade-value", type=float, default=1000)

    for p in (pm, pz):
        p.add_argument("--data", nargs="+", required=True, help="CODE:CSV路径，多个")
        p.add_argument("--start", required=True)
        p.add_argument("--end", required=True)
        p.add_argument("--cash", type=float, default=100000)
        p.add_argument("--comm", type=float, default=0.0001)
        p.add_argument("--index", default="000300.SH")
        p.add_argument("--outdir", default="./backtest_results")
    return ap


def main() -> None:
    a = build_parser().parse_args()
    {"mom": run_mom, "zcph": run_zcph}[a.engine](a)


if __name__ == "__main__":
    main()
