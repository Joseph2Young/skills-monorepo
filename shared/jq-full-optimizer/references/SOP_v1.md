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

### 4.2a 上传验证门控（关键）

**问题**：`jqcli strategy edit` 可能不生效——返回的 ID 可能不是实际更新的策略（`_find_strategy_by_name` 会找同名策略）。

**必须执行以下验证步骤**：

1. 上传代码后，从编辑页重新读取代码（GET /algorithm/index/edit）
2. 用 `parse_strategy_edit_html()` 解析返回的 `save_id`
3. 比对上传代码的前 20 行和重新读取的前 20 行
4. **用原始 strategy_id（非返回 ID）提交回测**
5. 如果比对不一致 → 警告用户，暂停流程

```python
def upload_with_verify(client, strategy_id, code):
    """上传策略代码并验证生效（read-back verify）"""
    # 1. 获取编辑页面
    html = client.get_text('/algorithm/index/edit', params={'algorithmId': strategy_id})
    detail = parse_strategy_edit_html(html, requested_id=strategy_id)
    payload = dict(detail['_form'])
    payload['algorithm[algorithmId]'] = str(detail['save_id'])
    payload['algorithm[code]'] = base64.b64encode(code.encode('utf-8')).decode('ascii')
    payload['encrType'] = 'base64'

    # 2. 上传
    client.post('/algorithm/index/save', data=payload,
                headers={'Referer': f'{client.api_base}/algorithm/index/edit?algorithmId={strategy_id}'})

    # 3. 验证（read-back）
    html2 = client.get_text('/algorithm/index/edit', params={'algorithmId': strategy_id})
    detail2 = parse_strategy_edit_html(html2, requested_id=strategy_id)
    saved_code = base64.b64decode(detail2['_form']['algorithm[code]']).decode('utf-8')

    # 4. 比对关键行
    uploaded_lines = code.strip().split('\n')[:20]
    saved_lines = saved_code.strip().split('\n')[:20]
    if uploaded_lines != saved_lines:
        raise ValueError("⚠️ 上传验证失败：代码不匹配！请检查策略 ID 是否正确。")

    print(f"✅ 上传验证通过 (strategy_id={strategy_id})")
    return strategy_id  # 用原始 ID，非 save_id
```

**检查点 CP-4.2a**：上传代码是否通过 read-back 验证？

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

### 5.0 择时条件开发子流程（可选）

> **适用场景**：需要**新增或替换**一个择时条件时，在 5.1 之前执行此子流程。如果只是验证现有条件的有效性，直接跳到 5.1。

#### 5.0.1 独立信号研究

**步骤**：
1. 编写独立研究脚本（不修改主策略），在聚宽平台运行
2. 在研究脚本中同时计算**新信号**和**旧信号**，对比触发时机
3. 标记关键极端时段（如大跌、大涨）的信号表现差异
4. 输出对比报告：信号触发次数、触发时段、极端期表现

**关键原则**：
- 独立脚本使用 `schedule` / `run_daily` 而非 `handle_data`，避免分钟级重复调用
- 独立脚本可以自由访问聚宽 API，不受主策略缓存层约束
- 独立脚本的结果仅作研究参考，不直接用于实盘

#### 5.0.2 信号参数预筛选

**步骤**：
1. 用独立脚本进行粗粒度参数扫描（4-8 组核心参数）
2. 确定参数大致合理区间
3. 避免在阶段六做全量搜索时范围过大

#### 5.0.3 集成到主策略

使用**集成清单**追踪主策略中所有需要修改的位置：

```markdown
## 集成清单模板

| # | 文件 | 行号 | 修改内容 | 状态 |
|---|------|------|---------|------|
| 1 | {strategy}.py | L{N} | 新增 `{condition}_enabled` 参数到 PARAMS | ⬜ |
| 2 | {strategy}.py | L{N} | 替换旧参数为新参数组 | ⬜ |
| 3 | {strategy}.py | L{N} | 新增 `{condition_name}()` 函数 | ⬜ |
| 4 | {strategy}.py | L{N} | 更新调用点引用（如 evaluate_morning_risk） | ⬜ |
| 5 | {strategy}.py | L{N} | 更新 _bull_to_bear() 中的引用 | ⬜ |
| 6 | {strategy}.py | L{N} | 更新 _bear_to_bull() 中的引用 | ⬜ |
| 7 | {strategy}.py | L{N} | 更新日志标签 | ⬜ |
| 8 | {strategy}.py | L{N} | 更新 schedule() 调用 | ⬜ |
```

**集成方法**：
1. 用 `grep` 搜索旧函数名，列出所有引用位置
2. 逐一修改并标注完成
3. 每处修改必须保持代码风格一致

#### 5.0.4 集成验证

- 修改后跑一次 sweep 回测，确认收益与独立脚本结果趋势一致
- 如果不一致 → 用集成清单逐项排查遗漏
- 特别检查：旧函数的所有引用是否都已替换

#### 5.0.5 同步更新扫描脚本

如果策略有配套的 sweep 扫描脚本，同步更新：
- 参数名变更（如 `old_param_enabled` → `new_param_enabled`）
- 新增参数的扫描定义
- 扫描脚本的 STRATEGY_ID 是否正确

**检查点 CP-5.0**：新择时条件是否已完成独立验证 + 集成 + 集成验证？（如跳过此步骤则不适用）

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
# 示例：均线择时策略的参数搜索空间
PARAM_GRID = {
    'ma_window': [10, 20, 30, 60],      # 均线窗口
    'threshold': [0.01, 0.03, 0.05],    # 信号阈值
    'hold_days': [3, 5, 10],            # 持仓天数
}

# 约束条件（根据策略逻辑自定义）
# 示例：持仓天数不应超过均线窗口的一半
def is_valid(params):
    return params['hold_days'] <= params['ma_window'] / 2
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

## 附录 D：API 返回值防御模板

### D.1 问题

聚宽 API（如 `get_backtest_result`）经常返回 `None`，直接使用 `f"{None:.4f}"` 会报 `TypeError`。

### D.2 通用防御函数

```python
def safe_fmt(val, fmt='.4f', default='N/A'):
    """安全格式化数值，None → 'N/A'"""
    return f"{val:{fmt}}" if val is not None else default

def safe_pct(val, default='N/A'):
    """安全百分比格式化"""
    return f"{val:.2f}%" if val is not None else default

def safe_int(val, default='N/A'):
    """安全整数格式化"""
    return str(int(val)) if val is not None else default
```

### D.3 使用示例

```python
# 提取回测指标
metrics = extract_metrics(bt_id)

# ❌ 危险：None 会触发 TypeError
print(f"Sharpe={metrics['sharpe']:.4f}")

# ✅ 安全：None → "N/A"
print(f"Sharpe={safe_fmt(metrics.get('sharpe'))}")
print(f"Return={safe_pct(metrics.get('total_return'))}")
print(f"MaxDD={safe_pct(metrics.get('max_drawdown'))}")
```

### D.4 提取函数模板

```python
def extract_metrics(bt_id):
    """从回测结果中提取指标（None 安全）"""
    rd = get_backtest_result(client, bt_id)
    data = rd.get('response', {}).get('data', rd.get('data', {}))

    ret_vals = data.get('result', {}).get('overallReturn', {}).get('value', [])
    sharpe_vals = data.get('result', {}).get('sharpe', {}).get('value', [])
    dd_vals = data.get('result', {}).get('maxDrawdown', {}).get('value', [])

    return {
        'total_return': ret_vals[-1] * 100 if ret_vals else None,
        'sharpe': sharpe_vals[-1] if sharpe_vals else None,
        'max_drawdown': abs(max(dd_vals)) * 100 if dd_vals else None,
    }
```

### D.5 结果 JSON 中的 None 处理规则

- 结果 JSON 中**允许 None 值存在**，不强制填充默认值
- None 表示"数据不可用"，比填充 0 更准确
- 排序时 None 排在最后：`sorted(results, key=lambda x: x.get('sharpe') or float('-inf'), reverse=True)`

---

## 附录 E：标准化扫描脚本骨架

### E.1 设计理念

每次扫描（消融实验、参数寻优等）都需要：并发控制、断点续跑、None 防御、结果持久化。本骨架将这些标准化为**填空式开发**——用户只需修改 CUSTOMIZE 区域（约 20 行），标准模块（约 100 行）自动处理一切。

### E.2 骨架代码

```python
"""
标准化扫描脚本骨架 v1.0
使用方法：复制本文件，修改 CUSTOMIZE 区域的变量即可
"""
import sys, json, time, base64, re
sys.path.insert(0, r'PATH_TO_JQCLI')
from jqcli.config import load_config, resolve_credentials
from jqcli.api.client import ApiClient
from jqcli.api.strategy import parse_strategy_edit_html
from jqcli.api.backtest import run_backtest, get_backtest_result, get_backtest_logs

# ============================================================
# CUSTOMIZE 区域 — 每次扫描只改这里
# ============================================================
STRATEGY_ID = 'YOUR_STRATEGY_ID'
BASE_CODE_PATH = r'PATH_TO_STRATEGY.py'
RESULTS_FILE = r'PATH_TO_results.json'  # 建议: jq_optimizer_workspace/phase{N}_xxx/results.json
BATCH_SIZE = 8           # 并发上限（聚宽限制 10，留 2 个缓冲）
POLL_INTERVAL = 60       # 轮询间隔（秒）
BACKTEST_START = '2017-01-01'
BACKTEST_END = '2026-05-31'
BACKTEST_CAPITAL = 1000000
BACKTEST_FREQ = 'minute'

# 扫描任务定义（按需修改）
# 格式：('结果 key', '描述', 参数修改函数)
TASKS = [
    # ('baseline', '基准', lambda code: code),
    # ('close_{cond}', '关闭{条件}', lambda code: modify_param(code, '{cond}_enabled', False)),
]

# ============================================================
# 标准模块（一般不用改）
# ============================================================
config = load_config()
token, cookie = resolve_credentials(config)
client = ApiClient(config.api_base, token=token, cookie=cookie, timeout=60)


def safe_fmt(val, fmt='.4f', default='N/A'):
    """安全格式化数值"""
    return f"{val:{fmt}}" if val is not None else default


def modify_param(code, key, value):
    """修改 PARAMS 字典中的布尔参数"""
    val_str = 'True' if value else 'False'
    lines = code.split('\n')
    new_lines = []
    for line in lines:
        if f"'{key}': " in line and line.strip().startswith("'"):
            new_lines.append(re.sub(rf"'{key}':\s*(True|False)", f"'{key}': {val_str}", line))
        else:
            new_lines.append(line)
    return '\n'.join(new_lines)


def modify_numeric_param(code, key, value):
    """修改 PARAMS 字典中的数值参数"""
    import re as _re
    lines = code.split('\n')
    new_lines = []
    for line in lines:
        if f"'{key}': " in line and line.strip().startswith("'"):
            new_lines.append(_re.sub(rf"'{key}':\s*[\d.]+", f"'{key}': {value}", line))
        else:
            new_lines.append(line)
    return '\n'.join(new_lines)


def retry(fn, *args, max_retries=3, **kwargs):
    """重试包装器"""
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(15 * (attempt + 1))
            else:
                raise


def upload_and_submit(code, label):
    """上传代码（含 read-back 验证）+ 提交回测"""
    html = retry(client.get_text, '/algorithm/index/edit',
                 params={'algorithmId': STRATEGY_ID})
    detail = parse_strategy_edit_html(html, requested_id=STRATEGY_ID)
    payload = dict(detail['_form'])
    payload['algorithm[algorithmId]'] = str(detail['save_id'])
    payload['algorithm[code]'] = base64.b64encode(code.encode('utf-8')).decode('ascii')
    payload['encrType'] = 'base64'
    retry(client.post, '/algorithm/index/save', data=payload,
          headers={'Referer': f'{client.api_base}/algorithm/index/edit?algorithmId={STRATEGY_ID}'})

    # read-back 验证（可选，如需严格验证可取消注释）
    # html2 = retry(client.get_text, '/algorithm/index/edit',
    #               params={'algorithmId': STRATEGY_ID})
    # detail2 = parse_strategy_edit_html(html2, requested_id=STRATEGY_ID)
    # saved = base64.b64decode(detail2['_form']['algorithm[code]']).decode('utf-8')
    # if code.strip().split('\n')[:20] != saved.strip().split('\n')[:20]:
    #     raise ValueError(f"上传验证失败: {label}")

    result = retry(run_backtest, client, strategy_id=STRATEGY_ID,
                   start_date=BACKTEST_START, end_date=BACKTEST_END,
                   capital=BACKTEST_CAPITAL, frequency=BACKTEST_FREQ)
    bt_id = (result.get('backtest_id') or result.get('id')
             or result.get('response', {}).get('data', {}).get('backtestId')
             or result.get('response', {}).get('data', {}).get('id'))
    print(f'  [{label}] BT ID: {bt_id}', flush=True)
    return bt_id


def extract_metrics(bt_id):
    """从回测结果中提取指标（None 安全）"""
    rd = retry(get_backtest_result, client, bt_id)
    data = rd.get('response', {}).get('data', rd.get('data', {}))
    ret_vals = data.get('result', {}).get('overallReturn', {}).get('value', [])
    sharpe_vals = data.get('result', {}).get('sharpe', {}).get('value', [])
    dd_vals = data.get('result', {}).get('maxDrawdown', {}).get('value', [])
    return {
        'total_return': ret_vals[-1] * 100 if ret_vals else None,
        'sharpe': sharpe_vals[-1] if sharpe_vals else None,
        'max_drawdown': abs(max(dd_vals)) * 100 if dd_vals else None,
    }


# ============================================================
# 主流程（断点续传 + 并发控制）
# ============================================================
# 加载已有结果（断点续跑）
completed = {}
try:
    with open(RESULTS_FILE, 'r') as f:
        saved = json.load(f)
        results_list = saved.get('results', saved) if isinstance(saved, dict) else saved
        for r in results_list:
            completed[r['key']] = r
        print(f"Loaded {len(completed)} existing results")
except Exception:
    pass

all_results = list(completed.values())
remaining = [(k, d, f) for k, d, f in TASKS if k not in completed]
total_tasks = len(TASKS)
print(f"Total: {total_tasks}, Completed: {len(completed)}, Remaining: {len(remaining)}")

# 分批提交 + 轮询
for batch_idx in range(0, len(remaining), BATCH_SIZE):
    batch = remaining[batch_idx:batch_idx + BATCH_SIZE]
    batch_num = batch_idx // BATCH_SIZE + 1
    total_batches = (len(remaining) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"\n{'='*60}")
    print(f"Batch {batch_num}/{total_batches}: {len(batch)} backtests")
    print(f"{'='*60}")

    submitted = []
    with open(BASE_CODE_PATH, 'r', encoding='utf-8') as f:
        base_code = f.read()

    for key, desc, modifier in batch:
        code = modifier(base_code)
        try:
            bt_id = upload_and_submit(code, desc)
            submitted.append((key, desc, bt_id))
            time.sleep(3)
        except Exception as e:
            print(f'  FAILED [{desc}]: {e}')

    # 轮询等待
    pending = list(submitted)
    while pending:
        still = []
        for key, desc, bt_id in pending:
            try:
                logs = retry(get_backtest_logs, client, bt_id, offset=0)
                state = str(logs.get('state', '?'))
                if state in ('2', '4'):
                    metrics = extract_metrics(bt_id)
                    result = {'key': key, 'desc': desc, 'bt_id': bt_id, **metrics}
                    all_results.append(result)
                    with open(RESULTS_FILE, 'w') as f:
                        json.dump({'results': all_results}, f, indent=2, ensure_ascii=False)
                    ret_str = f"{metrics['total_return']:.0f}%" if metrics['total_return'] else "N/A"
                    print(f'  DONE [{desc}] Ret={ret_str} Sharpe={safe_fmt(metrics.get("sharpe"))}')
                elif state == '3':
                    all_results.append({'key': key, 'desc': desc, 'bt_id': bt_id,
                                        'total_return': None, 'sharpe': None, 'max_drawdown': None})
                    with open(RESULTS_FILE, 'w') as f:
                        json.dump({'results': all_results}, f, indent=2, ensure_ascii=False)
                    print(f'  FAILED [{desc}]')
                else:
                    still.append((key, desc, bt_id))
            except Exception:
                still.append((key, desc, bt_id))
        pending = still
        if pending:
            print(f'  {len(all_results)}/{total_tasks} done, {len(pending)} pending...')
            time.sleep(POLL_INTERVAL)

# 最终报告
print(f"\n{'='*70}")
print(f"FINAL REPORT — {len(all_results)} results")
print(f"{'='*70}")
for r in sorted(all_results, key=lambda x: x.get('total_return') or float('-inf'), reverse=True):
    ret_str = f"{r['total_return']:.0f}%" if r.get('total_return') else "N/A"
    sharpe_str = safe_fmt(r.get('sharpe'))
    print(f"  {r.get('desc', r['key']):<20} Ret={ret_str:>10} Sharpe={sharpe_str}")
```

### E.3 使用示例

**消融实验**：

```python
TASKS = [
    ('baseline', '基准(全开)', lambda code: code),
    ('close_signal_score', '关闭信号评分',
     lambda code: modify_param(code, 'signal_score_enabled', False)),
    ('close_market_widen', '关闭市场宽度',
     lambda code: modify_param(code, 'market_widen_enabled', False)),
]
```

**参数扫描**：

```python
TASKS = []
for td in [2, 3, 4, 5]:
    for chg in [1.0, 2.0, 3.0, 5.0]:
        for pct in [50, 60, 70, 80]:
            key = f"td{td}_chg{chg}_pct{pct}"
            def make_modifier(t, c, p):
                def mod(code):
                    code = modify_numeric_param(code, 'trend_days', t)
                    code = modify_numeric_param(code, 'change_threshold', c)
                    code = modify_numeric_param(code, 'percentile', p)
                    return code
                return mod
            TASKS.append((key, f"td={td},chg={chg},pct={pct}", make_modifier(td, chg, pct)))
```

---

## 附录 F：数据流与 Workspace 文件管理规范

### F.1 Workspace 目录结构

所有过程产物统一保存到策略文件同目录下的 `jq_optimizer_workspace/`：

```
{策略文件同目录}/jq_optimizer_workspace/
├── manifest.json                     # 📋 总索引
├── phase1_deconstruct.md             # 阶段 1 报告
├── phase2_refactor.md                # 阶段 2 报告
├── phase3_cache_design.md            # 阶段 3 报告
├── phase4_collect/
│   ├── phase4_report.md              # 阶段 4 报告
│   └── cache_status.json             # 缓存完整性检查
├── phase5_validation/
│   ├── phase5_report.md              # 阶段 5 报告
│   ├── ablation_results.json         # 消融实验结果
│   └── sensitivity_results.json      # 敏感性分析结果
├── phase6_sweep/
│   ├── phase6_report.md              # 阶段 6 报告
│   └── sweep_results.json            # 参数扫描结果
├── phase7_robustness/
│   ├── phase7_report.md              # 阶段 7 报告
│   └── robustness_results.json       # 稳健性检验结果
├── phase8_report/
│   └── final_report.md               # 最终交付报告
└── scripts/                          # 扫描脚本存档
    ├── ablation_scan.py
    └── param_sweep.py
```

### F.2 manifest.json 总索引

```json
{
  "strategy_name": "策略文件名",
  "strategy_file": "策略文件完整路径",
  "algo_id": "聚宽策略ID",
  "created_at": "ISO8601时间",
  "current_phase": 6,
  "phases": {
    "1": {"status": "completed", "report": "phase1_deconstruct.md", "completed_at": "..."},
    "2": {"status": "completed", "report": "phase2_refactor.md", "completed_at": "..."},
    "3": {"status": "completed", "report": "phase3_cache_design.md", "completed_at": "..."},
    "4": {"status": "completed", "report": "phase4_collect/phase4_report.md", "completed_at": "..."},
    "5": {"status": "completed", "report": "phase5_validation/phase5_report.md", "completed_at": "..."},
    "6": {"status": "in_progress", "report": null, "completed_at": null}
  },
  "artifacts": [
    {"path": "phase4_collect/cache_status.json", "phase": 4, "type": "result", "description": "缓存完整性检查"},
    {"path": "phase5_validation/ablation_results.json", "phase": 5, "type": "result", "description": "消融实验结果"},
    {"path": "phase6_sweep/sweep_results.json", "phase": 6, "type": "result", "description": "参数扫描结果"}
  ]
}
```

### F.3 文件命名规范

| 类型 | 命名规则 | 示例 |
|------|---------|------|
| 阶段报告 | `phase{N}_report.md` | `phase5_report.md` |
| 结果文件 | `{experiment}_results.json` | `ablation_results.json` |
| 断点文件 | `{experiment}_checkpoint.json` | `sweep_checkpoint.json` |
| 扫描脚本 | `scripts/{purpose}_scan.py` | `scripts/param_sweep.py` |
| 状态文件 | `{experiment}_status.json` | `cache_status.json` |

### F.4 文件生命周期

| 阶段 | 产物 | 保留策略 |
|------|------|---------|
| 1-3 | 阶段报告 | 永久保留 |
| 4 | cache_status.json | 永久保留 |
| 5 | ablation/sensitivity JSON | 永久保留 |
| 6 | sweep_results.json | 永久保留 |
| 6 | sweep_checkpoint.json | 阶段完成后可清理 |
| 7 | robustness_results.json | 永久保留 |
| 8 | final_report.md | 永久保留（最终交付物） |
| all | scripts/*.py | 永久保留（存档，便于复现） |

### F.5 断点恢复流程

```
1. 读取 manifest.json → 确定 current_phase
2. 读取最近完成的 phase{N}_report.md → 了解上一阶段产出
3. 检查当前阶段的中间产物：
   ├── 有 *_results.json → 统计已完成数，从断点续跑
   ├── 有 *_checkpoint.json → 恢复 active/pending/remaining 状态
   └── 什么都没有 → 从头开始当前阶段
4. 向用户报告恢复状态，确认后继续
```

---

## 附录 G：阶段报告模板

每个阶段完成时生成标准化报告，既是交付物也是断点恢复的可视化标记。

```markdown
# 阶段 {N}：{阶段名称}

> 生成时间: {YYYY-MM-DD HH:MM}
> 策略: {策略文件名}
> 状态: {completed | skipped | failed}

## 关键产出

- 产出 1
- 产出 2
- ...

## 关键数据

| 指标 | 值 |
|------|-----|
| {指标名} | {值} |
| ... | ... |

## 遇到的问题

1. {问题描述} → {解决方案}
2. ...

## 下一阶段输入

- 阶段 {N+1} 需要的前置条件: {条件}
- 关键参数/配置: {参数}

## 产物文件

- `{相对路径}` — {用途说明}
- `{相对路径}` — {用途说明}

## 检查点状态

- [x] CP-{N}.1: {描述}
- [x] CP-{N}.2: {描述}
- [ ] CP-{N}.3: {描述}（如有未通过项）
```

### 各阶段报告的关键产出要求

| 阶段 | 报告中必须包含的产出 |
|------|-------------------|
| 1 | API 调用清单、模块依赖图、可调参数表 |
| 2 | PARAMS 字典、开关列表、函数解构图 |
| 3 | 缓存键列表、拦截点列表、meta 数据结构 |
| 4 | 缓存文件数 vs 交易日数、meta 数据摘要 |
| 5 | 消融实验结果表（贡献度排序）、敏感性曲线数据 |
| 6 | 参数扫描结果表（Top N）、最优参数是否在边界 |
| 7 | 样本内外对比、参数扰动结果、极端行情表现 |
| 8 | 完整报告（最终交付物） |

---

## 附录 H：通用使用建议

### H.1 参数修改工具函数

骨架脚本提供了两个参数修改函数，适用于不同场景：

| 函数 | 适用场景 | 示例 |
|------|---------|------|
| `modify_param(code, key, bool_value)` | 修改布尔开关 | `modify_param(code, 'signal_score_enabled', False)` |
| `modify_numeric_param(code, key, num_value)` | 修改数值参数 | `modify_numeric_param(code, 'lookback', 30)` |

对于更复杂的参数修改（如列表、字典），可以自定义修改函数：

```python
def modify_list_param(code, key, value):
    """修改 PARAMS 字典中的列表参数"""
    import re
    pattern = rf"'{key}':\s*\[.*?\]"
    replacement = f"'{key}': {value}"
    return re.sub(pattern, replacement, code)
```

### H.2 并发控制最佳实践

1. **MAX_CONCURRENT 永远设为 8**，不是 10——留 2 个缓冲槽避免边界情况
2. **提交间隔 3 秒**——避免短时间内大量请求被聚宽限流
3. **轮询间隔 60 秒**——sweep 回测 3-10 分钟，60 秒粒度足够
4. **指数退避**——遇到"超过 10 个"错误时，30s → 60s → 120s → 300s
5. **队列满 ≠ 失败**——放回 pending 队列，不记录为 error

### H.3 结果分析建议

```python
# 按收益排序（None 排最后）
sorted_results = sorted(all_results,
    key=lambda x: x.get('total_return') or float('-inf'), reverse=True)

# 计算贡献度（消融实验）
baseline_ret = next(r['total_return'] for r in all_results if r['key'] == 'baseline')
for r in all_results:
    if r['key'] != 'baseline' and r.get('total_return') is not None:
        r['contribution'] = r['total_return'] - baseline_ret

# 筛选有效结果（非 None）
valid_results = [r for r in all_results if r.get('total_return') is not None]
```

---

## 版本历史

| 版本 | 日期 | 修改内容 |
|------|------|---------|
| v2.0 | 2026-06-13 | 重大更新：新增上传验证门控(CP-4.2a)、择时条件开发子流程(5.0)、API防御模板(附录D)、扫描脚本骨架(附录E)、Workspace文件管理(附录F)、阶段报告模板(附录G)、通用建议(附录H) |
| v1.3 | 2026-05-28 | 修复并发控制：阶段五/六增加队列满处理、重试策略、断点续跑；MAX_CONCURRENT 从 10 改为 8 |
| v1.2 | 2026-05-27 | 移除 IC 检验，阶段五简化为择时条件开关验证+参数敏感性 |
| v1.1 | 2026-05-27 | 新增复权规则(3.2a)、参数无关/相关原则(3.3a)、实战陷阱附录(B) |
| v1.0 | 2026-05-27 | 初始版本，基于实战经验泛化 |

---

*本文档由 Claude Code 协助起草，需经用户审核确认后生效。*
