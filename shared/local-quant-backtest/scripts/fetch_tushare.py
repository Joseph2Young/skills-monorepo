#!/usr/bin/env python3
"""Tushare 取数 → 标准回测数据 CSV。

用法:
    export TUSHARE_TOKEN=xxxx
    python scripts/fetch_tushare.py --code 513100.SH --start 20250101 --end 20260902 --outdir ./data
    python scripts/fetch_tushare.py --code 000300.SH --index --start 20250101   # 指数

产出 CSV 列: date,open,high,low,close,volume(,preClose,zdf,amount)
- 股票/ETF: daily / fund_daily，股票自动前复权（adj_factor）
- 指数: index_daily
token 优先级: 环境变量 TUSHARE_TOKEN > ~/.tushare/token 文件"""
import argparse
import os
import sys


def get_token() -> str:
    tok = os.environ.get("TUSHARE_TOKEN", "").strip()
    if tok:
        return tok
    p = os.path.expanduser("~/.tushare/token")
    if os.path.exists(p):
        tok = open(p).read().strip()
        if tok:
            return tok
    sys.exit("未找到 TUSHARE_TOKEN（环境变量或 ~/.tushare/token）")


def fetch(code: str, start: str, end: str, is_index: bool):
    import pandas as pd
    import tushare as ts
    pro = ts.pro_api(get_token())
    if is_index:
        df = pro.index_daily(ts_code=code, start_date=start, end_date=end)
    elif code.upper().endswith((".SZ", ".SH")) and code[:2].isdigit() and code[:2].startswith(("5", "1")):
        df = pro.fund_daily(ts_code=code, start_date=start, end_date=end)  # ETF/LOF
    else:
        df = pro.daily(ts_code=code, start_date=start, end_date=end)
        adj = pro.adj_factor(ts_code=code, start_date=start, end_date=end)[["trade_date", "adj_factor"]]
        df = df.merge(adj, on="trade_date", how="left")
        for col in ("open", "high", "low", "close"):
            df[col] = df[col] * df["adj_factor"]  # 前复权
    if df is None or df.empty:
        sys.exit(f"{code} 取数为空")
    df = df.rename(columns={"trade_date": "date", "vol": "volume"})
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    df["preClose"] = df["close"].shift(1)
    df["zdf"] = df["close"].pct_change() * 100
    cols = ["date", "open", "high", "low", "close", "volume", "preClose", "zdf"]
    if "amount" in df.columns:
        cols.append("amount")
    return df[cols]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True, help="ts_code，如 513100.SH / 000300.SH")
    ap.add_argument("--start", default="20200101")
    ap.add_argument("--end", default="")
    ap.add_argument("--index", action="store_true", help="指数代码走 index_daily")
    ap.add_argument("--outdir", default="./data")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    df = fetch(a.code, a.start, a.end or "20991231", a.index)
    out = os.path.join(a.outdir, f"{a.code.replace('.', '_')}.csv")
    df.to_csv(out, index=False, encoding="utf-8")
    print(f"OK {a.code}: {len(df)} 行 {df['date'].min().date()} ~ {df['date'].max().date()} -> {out}")


if __name__ == "__main__":
    main()
