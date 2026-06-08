# 聚宽策略标准化优化 SOP v1.0

> 适用范围：所有聚宽（JoinQuant）量化策略的解耦、缓存加速、因子验证、参数寻优与报告撰写。
> 本流程从接收原始策略到输出最终报告，涵盖 8 个阶段、27 个检查点。

---

## 目录

1. [阶段一：策略解构](#阶段一策略解构)
2. [阶段二：架构重构](#阶段二架构重构)
3. [阶段三：缓存层设计](#阶段三缓存层设计)
4. [阶段四：Collect 模式运行](#阶段四collect-模式运行)
5. [阶段五：择时有效性验证](#阶段五择时有效性验证)
6. [阶段六：参数寻优](#阶段六参数寻优)
7. [阶段七：稳健性检验](#阶段七稳健性检验)
8. [阶段八：报告撰写](#阶段八报告撰写)
9. [附录 A：缓存键命名规范](#附录-a缓存键命名规范)
10. [附录 B：jqcli 常用命令速查](#附录-bjqcli-常用命令速查)
11. [附录 C：检查清单](#附录-c检查清单)

---

## 阶段一：策略解构

### 1.1 读取原始策略代码

**输入**：用户提供的 `.py` 策略文件
**输出**：策略结构分析报告

```
步骤：
1. 读取完整策略代码
2. 识别聚宽入口函数：initialize()、before_trading()、trade()、after_trading()
3. 识别所有定时任务：run_daily、run_weekly、run_monthly
4. 统计 API 调用清单（见 1.2）
5. 识别所有全局变量（g.*）及其生命周期
```

**检查点 CP-1.1**：是否完整识别了所有 API 调用？

### 1.2 API 调用分类

将策略中所有 API 调用分为三类：

| 类别 | 典型 API | 是否需缓存 | 原因 |
|------|---------|-----------|------|
| **高频大数据** | `get_price`、`get_bars`、`get_fundamentals` | ✅ 是 | 网络 IO 大，调用次数多 |
| **低频小数据** | `get_index_stocks`、`get_all_securities` | ⚠️ 可选 | 数据量小，但重复调用 |
| **框架内置** | `get_current_data`、`get_trade_days` | ❌ 否 | 框架本地处理，极快 |

**步骤**：
```bash
# 使用 grep 统计 API 调用
grep -n "get_price\|get_bars\|get_fundamentals\|get_index_stocks\|get_current_data" strategy.py
```

**检查点 CP-1.2**：是否对所有 `get_price`/`get_bars`/`get_fundamentals` 做了缓存规划？

### 1.3 识别核心模块

将策略逻辑分解为以下模块：

```
模块清单模板：
├── 选股模块 (Stock Selection)
│   ├── 股票池过滤
│   ├── 因子计算
│   └── 排序/评分
├── 择时模块 (Market Timing)
│   ├── 牛熊判断
│   ├── 风控信号
│   └── 仓位调整
├── 交易执行模块 (Execution)
│   ├── 买入逻辑
│   ├── 卖出逻辑
│   └── 调仓逻辑
└── 辅助模块 (Utilities)
    ├── 数据预处理
    ├── 日志/通知
    └── 风控检查
```

**检查点 CP-1.3**：每个模块的输入/输出是否清晰？

### 1.4 识别可调参数

**步骤**：
1. 列出所有硬编码数字（magic numbers）
2. 区分：策略逻辑常数 vs 可调超参数
3. 对每个可调参数，标注：含义、合理范围、默认值

```python
# 参数识别模板
PARAMS = {
    # 择时参数
    'signal_period': 5,          # 信号计算周期 [1, 60]
    'ma_window': 20,             # 均线窗口 [5, 120]
    'threshold': 0.1,            # 阈值 [0.01, 0.5]
    
    # 选股参数
    'stock_num': 10,             # 持仓数量 [1, 50]
    'weights': [1.0, ...],       # 因子权重（需归一化）
    
    # 风控参数
    'max_drawdown_limit': 0.2,   # 最大回撤限制 [0.05, 0.5]
    'position_ratio': 0.95,      # 仓位上限 [0.5, 1.0]
}
```

**检查点 CP-1.4**：每个参数是否有明确的物理含义和合理范围？

---

## 阶段二：架构重构

### 2.1 设计 PARAMS 字典

**原则**：
- 所有可调参数集中到 **一个** `PARAMS` 字典
- 每个参数有注释说明含义和范围
- 使用 `g.timing_params = PARAMS.copy()` 在 `initialize()` 中复制到全局

```python
# 反模式：分散的硬编码参数
# context.g.ma_window = 20  # ❌
# context.g.threshold = 0.1  # ❌

# 正模式：集中到 PARAMS
PARAMS = {
    'ma_window': 20,
    'threshold': 0.1,
}
# g.timing_params = PARAMS.copy()  # ✅
```

**检查点 CP-2.1**：策略中是否还有任何硬编码数字不在 PARAMS 中？

### 2.2 设计择时开关

**原则**：
- 每个择时条件设计独立的 `enabled` 开关
- 开关为布尔值，默认 `True`
- 开关命名规范：`{condition_name}_enabled`

```python
PARAMS = {
    # 择时开关
    'signal_score_enabled': True,
    'market_widen_enabled': True,
    'liquidity_crash_enabled': True,
    'ma_trend_enabled': False,      # 默认关闭的可选条件
    
    # 对应参数
    'signal_score_bull_threshold': 1,
    'signal_score_period': 5,
    # ...
}
```

**检查点 CP-2.2**：每个择时条件是否都能独立开关而不影响其他条件？

### 2.3 解耦为独立函数

**原则**：
- 每个择时条件解耦为独立函数
- 每个选股步骤解耦为独立函数
- 函数之间通过参数传递，不依赖全局状态（必要时除外）

```python
# 反模式：嵌套在 trade() 中的庞大逻辑
def trade(context):
    # 200 行混合逻辑... ❌

# 正模式：独立函数
def evaluate_morning_risk(context):
    """早盘风控检查"""
    if not g.timing_params['signal_score_enabled']:
        return False
    # ...
    return should_clear

def evaluate_midday_risk(context):
    """午间风控检查"""
    # ...

def evaluate_bull_bear(context):
    """尾盘牛熊判断"""
    # ...

def get_stock_list(context):
    """选股逻辑"""
    # ...
    return target_list
```

**检查点 CP-2.3**：`trade()` 函数是否不超过 30 行？

### 2.4 消除类层次结构（如适用）

**原则**：
- 将类方法重构为独立函数
- 类的 `__init__` 参数转为 PARAMS 条目
- 类的状态转为全局变量或函数参数

```python
# 反模式：类层次
timing_engine = TimingEngine(config)
result = timing_engine.evaluate(context)  # ❌

# 正模式：独立函数
g.timing_params = PARAMS.copy()
result = evaluate_bull_bear(context)  # ✅
```

**检查点 CP-2.4**：是否消除了不必要的类包装？

---

## 阶段三：缓存层设计

### 3.1 三模式设计

```python
CACHE_MODE = 'collect'  # 'live' | 'collect' | 'sweep'
```

| 模式 | 触发条件 | 行为 | IO |
|------|----------|------|-----|
| **live** | 正常回测/实盘 | 正常 API 调用，不缓存 | 正常 |
| **collect** | 首次回测，生成缓存 | 拦截 API 返回值，保存到每日 pkl | 每天 1 写 |
| **sweep** | 参数扫描，已有缓存 | 从缓存恢复数据，零 API 调用 | 每天 1 读 |

### 3.2 缓存键命名规范

**格式**：`{HH:MM}__{function_name}__{data_type}`

| 时间点 | 缓存键示例 | 数据类型 |
|--------|-----------|---------|
| 09:00 | `09:00__index_stocks` | list |
| 09:00 | `09:00__micro_pool` | list |
| 09:45 | `09:45__signal_bars` | DataFrame |
| 11:25 | `11:25__limit_check` | tuple |
| 14:57 | `14:57__market_widen` | dict |
| 14:57 | `14:57__stock_factors` | DataFrame |

### 3.2a 复权处理规则（关键）

**规则：缓存中所有价格数据统一使用后复权 `fq='post'`，另存一份 `fq=None` 的原始价用于现价/涨跌停匹配。**

| 用途 | fq 设置 | 原因 |
|------|---------|------|
| 收益率计算（选股评分） | `fq='post'` | 包含分红收益，排名更准确 |
| 指数涨跌幅 | `fq='post'` | 同上 |
| 当前现价（选股排序） | `fq=None` | 实际交易价格 |
| 涨跌停检测（`close == high_limit`） | `fq=None` | `high_limit` 是原始价格，不复权才能匹配 |
| 成交额/成交量 | 不受 fq 影响 | 任意值 |

**为什么后复权适合缓存**：

后复权价格的计算公式为：`adjusted_price_T = raw_price_T × ∏(因子, 除权日 ≤ T)`

公式中只依赖 T 之前发生的除权事件。未来新增的除权事件（除权日 > T）不会改变日期 T 的后复权价格。

| 复权方式 | 未来新除权是否影响历史价格 T？ | 缓存稳定性 |
|---------|---------------------------|-----------|
| 后复权 `fq='post'` | 不影响（公式只看 T 之前的事件） | **稳定** ✅ |
| 前复权 `fq='pre'` | 全部影响（公式依赖 T 之后的所有事件） | **不稳定** ❌ |
| 不复权 `fq=None` | 不影响 | 稳定 ✅ |

**缓存中的价格存储**：
```python
daily_cache = {
    '{time}__hist_post': DataFrame,    # 后复权价，算收益率用
    '{time}__current_raw': dict,       # 原始价（fq=None），现价/涨跌停用
}
```

**检查点 CP-3.1a**：所有 `get_price`/`get_bars` 调用是否使用了正确的 fq 设置？

**检查点 CP-3.1**：每个 API 调用是否有唯一且规范的缓存键？

### 3.3 缓存拦截模式

```python
def example_function(context):
    tp = str(context.current_dt)[-8:]
    cache_key = '{0}__example'.format(tp[:5] if tp >= '11:00' else '09:45')
    
    # sweep 模式：从缓存恢复
    if CACHE_MODE == 'sweep' and g.cache_dict and cache_key in g.cache_dict:
        return g.cache_dict[cache_key]
    
    # 正常逻辑（collect 或 live）
    result = expensive_api_call(...)
    
    # collect 模式：保存到缓存
    if CACHE_MODE == 'collect':
        g.cache_dict[cache_key] = result
    
    return result
```

**检查点 CP-3.2**：每个含 API 调用的函数是否都有 sweep 恢复 + collect 保存？

### 3.3a 参数无关 vs 参数相关（关键设计原则）

缓存设计必须明确区分两类数据，否则 sweep 模式无法正确工作。

**参数无关（缓存一次，所有参数组合复用）**：
原始市场数据，不受策略参数影响。这些数据在 collect 时获取一次，sweep 时直接读取。

| 数据类型 | 示例 |
|---------|------|
| 股票池列表 | `get_index_stocks()` 结果 |
| 价格序列 | `get_price()` 返回的收盘价 |
| 基本面数据 | `get_fundamentals()` 返回的市值/PE |
| 成交量/额 | `get_price()` 返回的 volume/money |
| 行业分类 | `get_industry()` 结果 |
| 涨跌停价 | `get_current_data()` 返回的 high_limit |
| 指数价格 | 微盘指数/HS300 日线 |

**参数相关（从缓存重算，不缓存结果）**：
基于原始数据的计算结果，不同参数值会产生不同结果。这些**不能**缓存，必须在 sweep 时从缓存的原始数据重算。

| 数据类型 | 示例 | 依赖参数 |
|---------|------|---------|
| 信号评分 | 行业虹吸得分 | lookback, forward, min_samples, count |
| 择时判断 | 牛/熊/震荡 | 各条件阈值、开关 |
| 选股排名 | 加权评分排序 | 因子权重 |
| 最终持仓 | 选出的 N 只股票 | stock_num, 排序逻辑 |

**设计原则**：
```
缓存只存"是什么"（原始数据），不存"算出来什么"（计算结果）。
参数变了，"是什么"不变，"算出来什么"会变。
所以缓存"是什么"，每次 sweep 从缓存重算"算出来什么"。
```

**具体判断方法**：问自己"如果改了 PARAMS 中的任何一个值，这个数据会变吗？"
- 不会变 → 参数无关 → 缓存
- 会变 → 参数相关 → 不缓存，从缓存数据重算

**CP-3.2a**：缓存字典中是否不存在任何参数相关的计算结果？

### 3.4 Meta 累积数据设计

**Meta 文件** (`meta.pkl.gz`) 存储跨日累积数据：

```python
meta = {
    'cumulative_data': DataFrame,  # 策略特定的时间序列指标
    'event_log': list,               # 事件日志
    'performance_log': list,         # 绩效日志
    'custom_history': list,          # 其他跨日历史数据
}
```

**保存时机**：collect 模式每天盘后保存（先于 daily_cache）

**检查点 CP-3.3**：meta 数据是否包含所有跨日累积状态？

### 3.5 断点续传设计

```python
def initialize(context):
    # sweep 和 collect 都加载已有 meta
    if CACHE_MODE in ('sweep', 'collect'):
        meta = load_meta_cache()
        if meta:
            g.cumulative_data = meta['cumulative_data']
            # ...

def trade(context):
    if current_time == '09:00:00':
        # collect 模式：已有缓存则跳过今日
        if CACHE_MODE == 'collect':
            existing = load_daily_cache(date_str)
            if existing is not None:
                g._skip_today = True
                return
```

**检查点 CP-3.4**：断点续传是否能正确识别已有缓存并跳过？

---

## 阶段四：Collect 模式运行

### 4.1 配置检查清单

运行 collect 前必须确认：

- [ ] `CACHE_MODE = 'collect'`
- [ ] `PARAMS` 中的参数为默认值或已知基准值
- [ ] 回测区间覆盖完整目标区间
- [ ] 回测频率正确（通常为 minute）
- [ ] 初始资金合理（通常为 1,000,000）
- [ ] 无其他并发回测（聚宽限制最多 10 个并行）

**检查点 CP-4.1**：collect 配置是否通过检查清单？

### 4.2 通过 jqcli 提交回测

```bash
# 1. 更新策略代码
jqcli strategy edit {algo_id} --file strategy.py

# 2. 提交回测（不等待）
jqcli backtest run {algo_id} \
  --start 2017-01-01 \
  --end 2026-05-26 \
  --capital 1000000 \
  --freq minute

# 3. 获取回测 ID，轮询状态
jqcli backtest show {bt_id}
```

**检查点 CP-4.2**：回测是否成功提交并 running？

### 4.3 监控与异常处理

**正常运行标志**：
- 回测状态为 `running`
- 日志中出现 `[缓存] 已保存 YYYY-MM-DD (N keys)`
- 研究环境中 缓存目录每天新增一个 `.pkl.gz` 文件

**异常情况处理**：

| 异常 | 原因 | 处理 |
|------|------|------|
| 状态 `failed` | 代码错误 | 检查日志，修复后重新提交 |
| 积分不足 | 免费额度用完 | 等待次日或购买积分后重新提交 |
| 缓存文件缺失 | 某日期保存失败 | 重新运行 collect，断点续传自动补充 |
| meta 损坏 | 文件写入中断 | 删除 meta.pkl.gz，从最近可用备份恢复 |

**检查点 CP-4.3**：是否每天检查缓存文件生成情况？

### 4.4 验证缓存完整性

Collect 完成后验证：

```python
# 检查每日缓存是否连续
import os
cache_files = sorted([f for f in os.listdir(cache_dir) if f.endswith('.pkl.gz')])
print(f'缓存文件数: {len(cache_files)}')

# 检查 meta 是否存在且非空
meta = load_meta_cache()
print(f'cumulative_data 行数: {len(meta["cumulative_data"])}')
print(f'event_log 条数: {len(meta["event_log"])}')
```

**检查点 CP-4.4**：缓存文件数量是否等于交易日数量？

---

## 阶段五：择时有效性验证

### 5.1 择时条件开关验证

**方法**：逐个关闭择时条件，用 sweep 跑回测，观察收益变化

#### 5.1a 并发控制（关键）

聚宽平台限制最多 **10 个并行回测**。阶段五的择时验证通常涉及 8-12 个条件，必须控制并发：

```python
MAX_CONCURRENT = 8  # 留 2 个槽位缓冲，避免"队列满"错误
POLL_INTERVAL = 30  # 秒

def run_timing_validation():
    base_result = run_sweep(all_enabled=True)  # 基准（第一个提交）
    jobs = {'baseline': base_result}
    
    for condition in timing_conditions:
        # 等待槽位释放
        while count_running(jobs) >= MAX_CONCURRENT:
            time.sleep(POLL_INTERVAL)
            update_job_status(jobs)
        
        # 提交下一个
        PARAMS[f'{condition}_enabled'] = False
        bt_id = submit_sweep(PARAMS)
        jobs[condition] = {'bt_id': bt_id, 'status': 'running'}
        PARAMS[f'{condition}_enabled'] = True  # 恢复
    
    # 等待全部完成
    wait_all_done(jobs)
```

**关键规则**：
- 每个条件测试前检查当前运行中回测数
- 达到 `MAX_CONCURRENT` 时主动等待，**不提交**
- 提交失败后（队列满）将该条件放回队列尾部，稍后重试

#### 5.1b 验证流程

```python
base_result = run_sweep(all_enabled=True)  # 基准

for condition in ['signal_score', 'market_widen', 'liquidity_crash', ...]:
    PARAMS = base_params.copy()
    PARAMS[f'{condition}_enabled'] = False
    result = run_sweep(PARAMS)
    contribution = base_result['sharpe'] - result['sharpe']
    PARAMS[f'{condition}_enabled'] = True  # 恢复
```

**分析维度**：
- 该条件对夏普的贡献（开启 vs 关闭的差异）
- 该条件对回撤的控制效果
- 该条件是否与其他条件冗余（关闭后夏普反而上升 → 冗余条件）

**检查点 CP-5.1**：每个择时条件的独立贡献是否量化？

### 5.2 参数敏感性分析

对每个关键参数，进行单边敏感性测试：

```python
# 示例：signal_score_period 敏感性
for period in [1, 3, 5, 10, 20, 30]:
    PARAMS['signal_score_period'] = period
    # 运行 sweep 回测，记录夏普
```

**输出**：敏感性曲线图（参数值 vs 夏普比率）

**检查点 CP-5.2**：核心参数是否有单调或单峰敏感性曲线？

---

## 阶段六：参数寻优

### 6.1 设计参数搜索空间

**原则**：
- 只搜索对收益影响大的参数
- 参数范围基于 5.3 敏感性分析结果
- 避免维度灾难（总组合数 < 200）

```python
PARAM_GRID = {
    'jsg_lookback': [20, 30, 40, 60],
    'jsg_forward': [1, 2, 3, 5],
    'jsg_min_samples': [2, 3],
    'jsg_count': [3, 5, 7],
}

# 约束条件
def is_valid(params):
    return params['jsg_lookback'] >= params['jsg_min_samples'] * 2
```

**检查点 CP-6.1**：参数搜索空间是否经过预筛选？

### 6.2 编写并发扫描脚本

#### 6.2a 并发控制策略（关键）

聚宽平台限制最多 **10 个并行回测**。阶段六的网格搜索通常涉及 50-200 个组合，必须实现**队列管理 + 错误重试**：

**核心原则**：
1. `MAX_CONCURRENT = 8` — 留 2 个槽位缓冲，避免提交时瞬间超限
2. **提交前检查** — 每次提交前确认当前运行中回测数 < MAX_CONCURRENT
3. **队列满错误处理** — 捕获"当前回测列表超过10个"错误，**不标记为失败**，放回队列稍后重试
4. **指数退避** — 连续遇到队列满时，等待时间递增（30s → 60s → 120s）

```python
MAX_CONCURRENT = 8       # 留缓冲
POLL_INTERVAL = 30       # 秒
MAX_RETRY = 3            # 单个组合最大重试次数

def run_sweep():
    completed = load_existing_results()  # 断点续跑
    combos = make_param_combinations()
    remaining = [c for c in combos if c not in completed]
    
    active = {}      # bt_id -> {params, status, retry_count}
    pending = []     # 因队列满而暂存的组合
    
    while active or pending or remaining:
        # 1. 检查活跃回测状态
        for bt_id in list(active.keys()):
            status = check_backtest(bt_id)
            if status == 'done':
                metrics = extract_metrics(bt_id)
                save_result(bt_id, metrics)
                del active[bt_id]
            elif status == 'failed':
                job = active[bt_id]
                if job['retry_count'] < MAX_RETRY:
                    job['retry_count'] += 1
                    pending.append(job['params'])  # 放回待重试
                del active[bt_id]
            # 'running' 则继续等待
        
        # 2. 补充新回测（严格检查并发数）
        while len(active) < MAX_CONCURRENT and (pending or remaining):
            params = pending.pop(0) if pending else remaining.pop(0)
            
            try:
                bt_id = submit_backtest(params)
                active[bt_id] = {
                    'params': params,
                    'status': 'running',
                    'retry_count': 0
                }
            except ApiError as e:
                if '超过' in str(e) or '最多' in str(e):
                    # 队列满，放回 pending，稍后重试
                    pending.insert(0, params)
                    break  # 停止提交，等待槽位释放
                else:
                    raise  # 其他错误直接抛出
            
            time.sleep(3)  # 避免提交过快
        
        # 3. 保存进度
        save_checkpoint(active, pending, remaining)
        
        if active or pending or remaining:
            print(f"进度: {len(completed)} 完成, {len(active)} 运行中, "
                  f"{len(pending)} 待重试, {len(remaining)} 待提交")
            time.sleep(POLL_INTERVAL)
```

#### 6.2b 断点续跑设计

扫描脚本必须支持断点续跑，避免中途失败导致全部重来：

```python
def save_checkpoint(active, pending, remaining):
    """保存当前进度到文件"""
    checkpoint = {
        'completed': load_completed_ids(),
        'active': {bt_id: job['params'] for bt_id, job in active.items()},
        'pending': pending,
        'remaining': remaining[:50],  # 只存前50个，避免文件过大
    }
    with open('sweep_checkpoint.json', 'w') as f:
        json.dump(checkpoint, f)

def load_existing_results():
    """加载已有结果"""
    if os.path.exists('sweep_results.json'):
        with open('sweep_results.json') as f:
            return json.load(f)
    return []
```

**检查点 CP-6.2**：并发脚本是否处理了聚宽并发限制错误？是否支持断点续跑？

### 6.3 结果分析与排序

**排序指标**：
1. 主要：夏普比率（风险调整后收益）
2. 次要：年化收益
3. 约束：最大回撤 < 30%

```python
def sort_results(results):
    # 过滤极端回撤
    valid = [r for r in results if r['max_drawdown'] < 0.30]
    # 按夏普排序
    valid.sort(key=lambda x: x['sharpe'], reverse=True)
    return valid
```

**输出**：Top N 参数组合表

**检查点 CP-6.3**：最优参数是否在搜索空间边界？（如果在边界，需扩展搜索）

---

## 阶段七：稳健性检验

### 7.1 样本外验证

**方法**：
- 用 2017-2022 数据优化参数
- 用 2023-2026 数据验证
- 对比样本内和样本外夏普差异

**判断标准**：样本外夏普 >= 样本内夏普 × 0.7

**检查点 CP-7.1**：样本外表现是否没有显著衰减？

### 7.2 参数稳健性

**方法**：在最优参数附近进行网格扰动：

```python
# 在最优参数 ±20% 范围内扰动
for delta in [-0.2, -0.1, 0, 0.1, 0.2]:
    perturbed = optimal_params * (1 + delta)
    # 运行回测
```

**判断标准**：参数扰动后夏普下降 < 20%

**检查点 CP-7.2**：最优参数附近是否存在"平坦区域"？

### 7.3 极端行情检验

**方法**：单独回测极端行情区间：

| 区间 | 行情特征 |
|------|---------|
| 2018-01 ~ 2019-01 | 熊市 |
| 2020-02 ~ 2020-04 | 疫情暴跌 |
| 2021-02 ~ 2021-03 | 抱团瓦解 |
| 2024-02 ~ 2024-09 | 快速反弹 |

**检查点 CP-7.3**：策略在极端行情中是否抗跌？

---

## 阶段八：报告撰写

### 8.1 报告结构

```
1. 策略概述
   1.1 核心逻辑
   1.2 适用市场
   1.3 风险等级

2. 重构过程
   2.1 原始策略分析
   2.2 解耦方案
   2.3 缓存架构

3. 择时有效性分析
   3.1 择时条件贡献度
   3.2 参数敏感性

4. 参数寻优结果
   4.1 搜索空间
   4.2 最优参数
   4.3 收益指标

5. 稳健性检验
   5.1 样本外验证
   5.2 参数稳健性
   5.3 极端行情表现

6. 风险提示与建议
   6.1 历史有效性不代表未来
   6.2 参数过拟合风险
   6.3 市场结构变化风险
```

### 8.2 关键图表

| 图表 | 用途 |
|------|------|
| 收益曲线对比图 | 原始 vs 优化后 |
| 参数敏感性热力图 | 双参数交互效应 |
| IC 时间序列图 | 因子稳定性 |
| 回撤分布图 | 风险特征 |
| 分年度收益表 | 年度稳健性 |

**检查点 CP-8.1**：报告是否包含至少 3 个关键图表？

### 8.3 合规声明

报告末尾必须包含：

```
风险提示：
1. 本报告仅供量化研究参考，不构成任何投资建议。
2. 策略历史回测表现不代表未来实际收益。
3. 市场环境变化可能导致策略失效。
4. 参数优化存在过拟合风险，需谨慎使用。
5. 投资有风险，入市需谨慎。
```

**检查点 CP-8.2**：是否包含合规风险提示？

---

## 附录 A：缓存键命名规范

### 时间前缀

| 前缀 | 含义 | 示例 |
|------|------|------|
| `09:00__` | 盘前准备数据 | `09:00__micro_pool` |
| `09:45__` | 早盘数据 | `09:45__signal_bars` |
| `11:25__` | 午间数据 | `11:25__limit_check` |
| `14:57__` | 尾盘数据 | `14:57__stock_factors` |

### 数据类型后缀

| 后缀 | 数据类型 | 示例 |
|------|---------|------|
| `_pool` | 股票列表 | `micro_pool` |
| `_bars` | K线DataFrame | `signal_bars` |
| `_check` | 检查结果 | `limit_check` |
| `_factors` | 因子DataFrame | `stock_factors` |
| `_derived` | 派生数据dict | `micro_derived` |

---

## 附录 B：常见陷阱与规避（实战经验）

### B.1 缓存键冲突

**陷阱**：同一函数在一天内被多个时间点调用，如果缓存键不带时间前缀，sweep 模式会返回错误时间点缓存的数据。

**实例**：`get_tiny_index()` 在 09:45 和 14:57 各调用一次，09:45 用的数据是开盘前的，14:57 用的是收盘前的。

**规避**：
```python
# ❌ 错误：缺少时间前缀
cache_key = 'tiny_index_1d'

# ✅ 正确：用时间点前缀
tp = str(context.current_dt)[-8:]
cache_key = '{}__tiny_index_1d'.format(tp[:5])  # '09:45__tiny_index_1d' 或 '14:57__tiny_index_1d'
```

### B.2 Sweep 模式污染累积数据

**陷阱**：sweep 模式运行时，如果代码中对累积列表（如 `g.event_log`）执行了 `append()`，多次 sweep 会导致数据无限膨胀。

**实例**：某策略的累积日志模块中，sweep 模式错误地对 `g.event_log` 执行了 append，导致 100 次 sweep 后日志条目膨胀了 100 倍。

**规避**：所有累积数据的写入都必须加模式判断：
```python
# ❌ 错误：sweep 模式下也会追加
g.event_log.append(new_event)

# ✅ 正确：只在 collect/live 模式下追加
if CACHE_MODE != 'sweep':
    g.event_log.append(new_event)
```

### B.3 Meta 保存顺序

**陷阱**：`after_market_close()` 中先保存 daily_cache 再保存 meta。如果 daily 保存成功但 meta 保存失败（例如积分不足或网络中断），累积数据会丢失。

**规避**：先保存 meta，再保存 daily_cache：
```python
# ✅ 正确顺序
save_meta_cache(...)       # 先保存累积数据
save_daily_cache(...)       # 再保存每日缓存
```

### B.4 hasattr 陷阱

**陷阱**：`hasattr(g, g.csv_name)` 其中 `csv_name = "simulation_file/test.csv"`，Python 将含 `/` 的字符串作为属性名时 `hasattr` 永远返回 `False`。

**规避**：检查数据本身而非属性名：
```python
# ❌ 错误
if hasattr(g, g.csv_name):  # 永远 False
    return

# ✅ 正确
if hasattr(g, 'data') and not g.data.empty:
    return
```

### B.5 聚宽平台限制与并发控制

| 限制 | 数值 | 应对策略 |
|------|------|---------|
| 最大并行回测 | 10 个 | 并发扫描脚本控制 `MAX_CONCURRENT=8`（留缓冲） |
| 单次回测时长 | 分钟频 ~5 小时 | 长区间 collect 可能接近上限 |
| 每日免费积分 | 有限 | 积分不足时等待次日或购买 |
| 研究环境存储 | ~5GB | 5年缓存约 1.5-2.5GB，需监控 |
| 并发提交错误 | "当前回测列表超过10个" | 捕获错误，放回队列，**不标记为 failed** |

#### 完整的队列满处理模板

```python
import time

MAX_CONCURRENT = 8
BACKOFF_DELAYS = [30, 60, 120, 300]  # 指数退避

def submit_with_retry(params, retry_count=0):
    """提交回测，带队列满重试"""
    try:
        bt_id = submit_backtest(params)
        return {'success': True, 'bt_id': bt_id}
    except ApiError as e:
        msg = str(e)
        # 判断是否为队列满（聚宽的错误提示可能变化）
        is_queue_full = any(kw in msg for kw in ['超过', '最多', '10个', '并发'])
        
        if is_queue_full and retry_count < len(BACKOFF_DELAYS):
            delay = BACKOFF_DELAYS[retry_count]
            print(f"队列满，等待 {delay} 秒后重试...")
            time.sleep(delay)
            return submit_with_retry(params, retry_count + 1)
        
        # 其他错误或重试耗尽
        return {'success': False, 'error': msg}

# 主循环中的使用
def run_grid_search():
    for params in combinations:
        # 等待槽位
        while count_running() >= MAX_CONCURRENT:
            time.sleep(30)
            update_running_status()
        
        # 提交（带重试）
        result = submit_with_retry(params)
        if result['success']:
            active_jobs[result['bt_id']] = params
        else:
            # 重试耗尽，记录为失败
            failed_jobs.append({'params': params, 'error': result['error']})
```

#### 阶段五与阶段六的并发策略差异

| 阶段 | 回测数 | 并发策略 | 等待策略 |
|------|--------|---------|---------|
| 阶段五（择时验证） | 8-12 个 | 逐个提交，每次检查槽位 | 队列满时暂停提交，等待完成后再继续 |
| 阶段六（参数寻优） | 50-200 个 | 批量提交到 MAX_CONCURRENT | 队列满时将剩余组合存入 pending，轮询补充 |

**关键原则**：
1. **绝不一次性提交超过 MAX_CONCURRENT 个回测**
2. **队列满错误 ≠ 失败** — 必须放回队列重试
3. **每次提交前检查当前运行中数量** — 不要假设之前提交的都已完成
4. **保存 checkpoint** — 支持断点续跑，避免全部重来

---

## 附录 C：jqcli 常用命令速查

```bash
# 策略管理
jqcli strategy ls --all                          # 列出所有策略
jqcli strategy edit {algo_id} --file strategy.py # 更新策略代码

# 回测管理
jqcli backtest run {algo_id} \
  --start 2020-01-01 --end 2025-12-31 \
  --capital 1000000 --freq minute               # 提交回测
jqcli backtest show {bt_id}                      # 查看回测状态
jqcli backtest stats {bt_id} --format json       # 获取回测统计
jqcli backtest logs {bt_id}                      # 查看回测日志

# 批量操作（脚本中）
python sweep_script.py     # 运行扫描脚本
```

---

## 附录 C：检查清单

### 最终交付检查清单

**架构**：
- [ ] 策略代码已解耦为独立函数
- [ ] PARAMS 字典包含所有可调参数
- [ ] 所有择时条件有独立开关
- [ ] trade() 函数不超过 30 行

**缓存**：
- [ ] 所有 `get_price`/`get_bars` 使用后复权 `fq='post'`
- [ ] 涨跌停检测使用 `fq=None`
- [ ] 缓存键使用 `{HH:MM}__` 时间前缀，无冲突
- [ ] 缓存中不存在参数相关的计算结果
- [ ] sweep 模式不修改累积数据（只读）
- [ ] meta 保存顺序：先 meta 后 daily
- [ ] 断点续传逻辑正确
- [ ] collect 模式成功生成完整缓存
- [ ] sweep 模式零 API 调用

**验证**：
- [ ] 择时条件贡献验证完成
- [ ] 参数寻优找到最优组合
- [ ] 稳健性检验通过
- [ ] 报告撰写完成，含合规声明

---

## 版本历史

| 版本 | 日期 | 修改内容 |
|------|------|---------|
| v1.3 | 2026-05-28 | 修复并发控制：阶段五/六增加队列满处理、重试策略、断点续跑；MAX_CONCURRENT 从 10 改为 8 |
| v1.2 | 2026-05-27 | 移除 IC 检验，阶段五简化为择时条件开关验证+参数敏感性 |
| v1.1 | 2026-05-27 | 新增复权规则(3.2a)、参数无关/相关原则(3.3a)、实战陷阱附录(B) |
| v1.0 | 2026-05-27 | 初始版本，基于实战经验泛化 |

---

*本文档由 Claude Code 协助起草，需经用户审核确认后生效。*
