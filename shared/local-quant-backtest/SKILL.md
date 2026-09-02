---
name: local-quant-backtest
description: 本地量化回测套件——四个纯本地回测/计算引擎（动量轮动、多因子排序选股、组合再平衡、通达信160函数库），数据由 Tushare/万得/通达信 MCP 自供，全程不依赖任何外部服务器。当主人要求"本地回测动量/轮动/因子选股/再平衡策略""算通达信指标"或提到小果引擎本地化时使用。
---

# 本地量化回测套件（local-quant-backtest）

四个**纯本地、零网络调用**的引擎（源自小果 xg_quant，已审计源码并实测），数据一律由主人自有数据源准备成标准 DataFrame 注入。**严禁**使用 `xg_quant_backtrader_data` 数据包或连接 124.220.32.224（作者服务器）。

## 引擎选型

| 引擎 | 用途 | 典型场景 |
|------|------|---------|
| `xg_mom_backtrader` | 动量轮动 | ETF/行业轮动，动量排名持有前N + 止盈 |
| `xg_zcph_backtrader` | 组合再平衡 | 目标权重 + 偏离阈值触发 + 20日定期 + 止损止盈 |
| `xg_rank_factor_backtrader` | 多因子排序选股 | 买入条件(and/or/not) + 因子加权排名轮动，支持自定义因子公式 |
| `xg_tdx_func` | 通达信函数库 | 160 个函数（MA/EMA/MACD/BOLL/KDJ/ZIG…），返回 numpy 数组，供因子计算和 rank 引擎复用 |

## 一次性环境安装

```bash
# 装进托管 venv（已含 pandas/numpy/pyarrow）
python scripts/install_wheels.py
```

脚本会：安装 4 个 wheel → 自动 patch 两处 pandas 3.x 兼容 bug（`fillna(method='ffill')` 已废弃写法，mom/zcph 引擎各一处）。幂等可重复执行。

## 数据契约（三源统一）

所有引擎要求每只标的一个 DataFrame，列：**date, open, high, low, close, volume**（必须）+ preClose, zdf（推荐，zcph 复权/涨跌停过滤用）。date 为 datetime，按日期升序去重。

| 优先级 | 数据源 | 做法 |
|--------|--------|------|
| 主 | **Tushare** | `python scripts/fetch_tushare.py --code 513100.SH --start 20250101`（股票自动前复权；ETF 走 fund_daily）。token 从环境变量 `TUSHARE_TOKEN` 读取。也可用 mcp__tushare__* 工具取数后由 AI 整理成 CSV |
| 备 | **万得 MCP** | mcp__wind-finance__get_stock_kline / get_index_kline 取数 → AI 整理为标准列 |
| 备 | **通达信 MCP / pytdx** | 取日线 → AI 整理为标准列 |

AI 整理数据时的列映射：tushare `trade_date→date, vol→volume`；wind `timetick→date`。取到的数据落 CSV（utf-8）再喂给回测脚本。

## 快速回测（CLI）

```bash
# 动量轮动：25日动量，持有第1名，3%止盈，万1佣金
python scripts/run_backtest.py mom \
  --data 513100.SH:/path/513100.csv 518880.SH:/path/518880.csv \
  --start 20250101 --end 20260902 --cash 100000 --comm 0.0001 \
  --mom-daily 25 --buy-rank 1 --sell-zdf 0.03

# 组合再平衡：目标权重 35/35/30，偏离10%触发，20日定期再平衡，±3%止损止盈
python scripts/run_backtest.py zcph \
  --data 513100.SH:... 518880.SH:... 159915.SZ:... \
  --weights 0.35 0.35 0.30 --deviation 0.10 --interval 20 \
  --buy-zdf -0.03 --sell-zdf 0.03
```

输出：绩效汇总（总收益/年化/回撤/Sharpe/胜率/手续费）+ 对比等权基准的超额 + 交易明细，落盘到 `--outdir`（默认 ./backtest_results）。

## AI 直接调引擎（复杂场景）

多因子排序引擎（rank）参数复杂，AI 写内联 Python 调用，参考 `references/engines.md` 完整示例：

```python
from xg_rank_factor_backtrader.xg_rank_factor_backtrader import xg_rank_factor_backtrader
bt = xg_rank_factor_backtrader(
    start_date="20250101", end_date="20260902",
    stock_list=["513100.SH", "518880.SH", "159915.SZ"],
    cash=100000, comm=0.0001,
    user_factor_cacal={  # 自定义因子公式，df 为行情表，可直接用 TDX 函数
        "收盘价大于5日均线": "IF(df['close']>MA(df['close'],5),0,1)",
    },
    buy_condi_factor={"收盘价大于5日均线": {"选择类型": "and", "选择方向": "等于", "值": 0}},
    # 排序因子配置见 references/engines.md
)
for code, df_path in data_map.items():
    bt.add_stock_data_from_dataframe(code, pd.read_csv(df_path, parse_dates=["date"]))
bt.run_backtest()
print(bt.get_performance_metrics())
```

## 已知坑位

- **pandas 3.x**：wheel 原版有两处 `fillna(method='ffill')` 会崩，install_wheels.py 已自动 patch；重装 wheel 后需重跑 patch
- **TDX 函数返回 numpy 数组**：不是 Series，链式计算用 `np.` 函数或转回 Series
- **引擎默认参数里 stock_list 是演示值**：必须显式传入
- **基准指数**：引擎会找本地 parquet 的指数数据，没有也能跑（基准曲线为空，超额对比跳过）；需要基准就把指数行情一并注入

## 红线

1. 禁止 import `xg_quant_backtrader_data`（连作者服务器，违反本地化原则）
2. 禁止把数据源写成他的 HTTP API；数据缺失直接标注，不造数
3. 回测结果仅供研究，引擎撮合逻辑未逐行审计（vectorized_backtest 约 300 行），重大决策前主人须复核成交价假设
