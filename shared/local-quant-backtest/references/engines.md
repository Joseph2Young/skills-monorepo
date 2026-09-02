# 引擎参数详解与示例

## 1. xg_mom_backtrader（动量轮动）

构造参数：

| 参数 | 默认 | 说明 |
|------|------|------|
| start_date / end_date | — | 回测区间 yyyymmdd |
| stock_list | 演示值 | 标的代码列表，必须显式传 |
| index_stock | 000300.SH | 基准指数 |
| cash / comm | 100000 / 0.0001 | 初始资金 / 佣金率 |
| mom_type / mom_value | 百分比 / 1.0 | 每次买入动用总资产比例 |
| mom_daily | 25 | 动量回看交易日数（加权线性回归斜率年化×R²） |
| min_mom / max_mom | 0 / 5 | 动量分数区间筛选（过滤过热与弱势，全落榜回退取第1名） |
| buy_rank | 1 | 持有动量排名前 N |
| sell_zdf / sell_amount | 0.03 | 当日涨幅≥3% 止盈，卖出金额 |

策略逻辑：每日打分→区间筛选→排名→先卖后买轮动→止盈。

## 2. xg_zcph_backtrader（组合再平衡）

| 参数 | 默认 | 说明 |
|------|------|------|
| weight_list | [0.35,0.35,0.3] | 各标的目标权重（与 stock_list 顺序对应） |
| deviation_list | [0.1,0.1,0.05] | 偏离阈值：实际权重偏离目标超阈值触发再平衡 |
| interval | 20 | 定期再平衡间隔（交易日） |
| sell_zdf / buy_zdf | 0.03 / -0.03 | 止盈/止损阈值（跌幅触发买入摊薄） |
| trade_value | 1000 | 止损买入金额 |
| use_custom_data | False | **必须传 True** 才走注入数据 |

数据推荐带 preClose、zdf 列（复权与涨跌停过滤）。

## 3. xg_rank_factor_backtrader（多因子排序选股）

三步逻辑：买入条件筛池（and/or/not）→ 排序因子加权排名 → 按买入排名轮动。

关键参数：

```python
user_factor_cacal = {  # 自定义因子公式，df 为行情表，可直接用 TDX 函数（来自 xg_tdx_func）
    "收盘价大于5日均线": "IF(df['close']>MA(df['close'],5),0,1)",   # Bool 因子：0=True 符合
    "25日回归动量": None,  # 引擎内置因子名可直接引用
}
buy_condi_factor = {   # 买入条件（Bool 因子 0=符合）
    "收盘价大于5日均线": {"选择类型": "and", "选择方向": "等于", "值": 0},
}
rank_factor = {        # 排序因子（示意，以引擎实际签名为准）
    "25日回归动量": {"方向": "正相关", "权重": 1.0},
}
# trader_type="百分比", trader_value=0.5, buy_rank=N, cash, comm
```

完整签名用 `inspect.signature(xg_rank_factor_backtrader.__init__)` 查看；内置因子名清单可读包内源码 `xg_rank_factor_backtrader.py` 的因子表构造段。

## 4. xg_tdx_func（通达信函数库）

- 160 个函数，全部返回 **numpy 数组**（不是 Series），入参用 `df['close'].values` 或 Series 均可
- 常用：MA EMA SMA MACD KDJ RSI BOLL HHV LLV REF COUNT CROSS ZIG SAR CYC …
- 用途：① 独立计算指标 ② 写 rank 引擎的 user_factor_cacal 公式
- DYNAINFO_*/FINANCE_* 系列需要实时/财务字段，回测场景不适用

## 性能指标口径

各引擎 get_performance_metrics() 返回：total_return / annual_return / max_drawdown / sharpe_ratio / win_rate / total_commission / excess_return_pct（vs 等权持有基准）。
