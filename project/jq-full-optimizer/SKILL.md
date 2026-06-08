---
name: jq-full-optimizer
description: 聚宽策略全流程优化器。涵盖策略解构、架构重构、缓存层设计（collect/sweep/live 三模式）、因子验证、参数寻优、稳健性检验到报告撰写的完整 8 阶段 SOP。适用于所有聚宽量化策略。Trigger when user wants to optimize, refactor, or add cache/sweep to a JoinQuant strategy.
---

# 聚宽策略全流程优化器

当用户输入 `/jq-full-optimizer` 时，按以下 8 阶段工作流推进。每个阶段末尾有检查点（CP），必须通过才能进入下一阶段。

> 详细参考文档：[SOP 正文](references/SOP_v1.md) | [流程图](references/SOP_流程图.md)
> 关系说明：本 Skill 是 `jq-optimizer`（纯参数搜索）的升级版，增加了缓存加速、因子验证、稳健性检验等阶段。对于已有缓存层的策略，Phase 6 使用 sweep 模式而非逐次 API 调用。

---

## 前置条件

### Step 1：检测 jqcli

运行 `jqcli --version` 或 `python -m jqcli --version` 检查是否已安装。

- **已安装** → 跳到 Step 3
- **未安装** → 进入 Step 2

### Step 2：安装 jqcli

询问用户：
1. "你本地是否已有 jqcli 项目？如果有，请提供路径。"
2. 如果用户说没有 → 询问安装到哪个 Python 环境（conda 环境名或虚拟环境路径）
3. 从 GitHub 安装：
   ```bash
   pip install git+https://github.com/breakhearts/jqcli.git
   ```
4. 如果用户提供了本地路径 → 用 `pip install -e <路径>` 以开发模式安装

安装完成后重新运行 Step 1 确认。

### Step 3：配置认证

询问用户是否已配置 jqcli 认证。运行 `jqcli auth status` 检查：

- **已认证** → 跳到 Step 4
- **未认证** → 引导用户配置：

凭据获取方式：
1. 登录聚宽网页版 https://www.joinquant.com
2. 打开浏览器开发者工具（F12）→ Network 面板
3. 刷新页面，找到任意请求的 `Cookie` 请求头 → 即为 `JQCLI_COOKIE`

配置方式（任选其一）：
```bash
# 方式 A：环境变量
export JQCLI_TOKEN=your_token
export JQCLI_COOKIE=your_cookie

# 方式 B：命令行参数（每次传递）
jqcli --token your_token --cookie your_cookie <command>

# 方式 C：auth login（交互式）
jqcli auth login
```

> **安全规则**：绝对不要将凭据写入代码文件或提交到版本控制。凭据优先级：命令行参数 > 环境变量 > 配置文件。

### Step 4：确认策略和回测信息

向用户确认以下信息：
1. **策略文件路径**：`.py` 策略文件的完整路径
2. **聚宽 algo_id**：用户直接提供，或通过 `jqcli strategy ls` 查找
3. **回测参数**：起止日期、初始资金、回测频率（day/minute）

所有前置条件满足后，进入阶段一。

---

## 阶段一：策略解构

### 1.1 读取并分析策略

读取完整策略代码，识别：

| 识别项 | 方法 | 输出 |
|--------|------|------|
| 入口函数 | grep `initialize\|before_trading_start\|handle_data\|after_trading_end` | 函数位置 |
| 定时任务 | grep `run_daily\|run_weekly\|run_monthly` | 时间点清单 |
| API 调用 | grep `get_price\|get_bars\|get_fundamentals\|get_index_stocks\|get_all_securities\|get_current_data\|get_extras\|get_industry` | API 清单 |
| 全局变量 | grep `g\.\w+` | 变量列表 |
| 硬编码数字 | 正则 `\b\d+\b` 在赋值/比较上下文中 | 可调参数候选 |

### 1.2 API 调用分类

将所有 API 调用分为三类：

| 类别 | 典型 API | 缓存必要性 |
|------|---------|-----------|
| 高频大数据 | `get_price`, `get_bars`, `get_fundamentals` | **必须缓存** |
| 低频小数据 | `get_index_stocks`, `get_all_securities`, `get_industry`, `get_extras` | 建议缓存 |
| 框架内置 | `get_current_data`, `get_trade_days`, `get_orders`, `get_positions` | 不缓存 |

### 1.3 模块分解

将策略逻辑分解为：

```
├── 选股模块 (Stock Selection)
│   ├── 股票池过滤
│   ├── 因子计算
│   └── 排序/评分
├── 择时模块 (Market Timing)
│   ├── 条件1 (独立)
│   ├── 条件2 (独立)
│   └── ...
├── 交易执行模块 (Execution)
│   ├── 买入逻辑
│   └── 卖出/调仓逻辑
└── 辅助模块 (Utilities)
    ├── 数据预处理
    └── 日志/风控
```

### 1.4 识别可调参数

输出参数表：

```
# | 参数 | 含义 | 当前值 | 合理范围 | 类型
1 | lookback | 均线窗口 | 20 | [5, 120] | int
2 | threshold | 信号阈值 | 0.1 | [0.01, 0.5] | float
...
```

**CP-1.1** ✅ 所有 API 调用已分类 | **CP-1.2** ✅ 模块输入输出清晰 | **CP-1.3** ✅ 参数表完整

---

## 阶段二：架构重构

### 2.1 PARAMS 字典

将所有可调参数集中到一个 `PARAMS` 字典：

```python
PARAMS = {
    # 择时开关
    'signal_score_enabled': True,
    'market_widen_enabled': True,
    # 择时参数
    'signal_period': 5,          # [1, 60]
    'ma_window': 20,             # [5, 120]
    # 选股参数
    'stock_num': 10,             # [1, 50]
    # 风控参数
    'max_position_ratio': 0.95,  # [0.5, 1.0]
}
```

在 `initialize()` 中：`g.params = PARAMS.copy()`

### 2.2 择时开关

每个择时条件设计独立 `enabled` 开关，命名规范 `{condition_name}_enabled`。

### 2.3 函数解耦

目标：`trade()` 函数不超过 30 行。每个择时条件和选股步骤为独立函数。

**CP-2.1** ✅ 无硬编码参数 | **CP-2.2** ✅ 每个条件可独立开关 | **CP-2.3** ✅ trade() ≤ 30 行

---

## 阶段三：缓存层设计

### 3.1 三模式

```python
CACHE_MODE = 'collect'  # 'live' | 'collect' | 'sweep'
```

| 模式 | 触发条件 | API 调用 | IO |
|------|----------|---------|-----|
| live | 正常回测/实盘 | 正常 | 正常 |
| collect | 首次，生成缓存 | 正常调用 | 每天 1 次 write_file |
| sweep | 参数扫描 | **零调用** | 每天 1 次 read_file |

### 3.2 复权规则（关键）

**缓存中所有价格数据统一使用后复权 `fq='post'`。**

| 用途 | fq 设置 | 原因 |
|------|---------|------|
| 收益率计算 | `fq='post'` | 包含分红，排名更准确 |
| 指数涨跌幅 | `fq='post'` | 同上 |
| 当前现价 | `fq=None` | 实际交易价 |
| 涨跌停检测 | `fq=None` | high_limit 是原始价 |

**后复权为什么缓存安全**：后复权价格 = raw_price × ∏(因子, 除权日≤T)。公式只依赖 T 之前的除权事件，未来新除权不会改变已缓存的历史价格。

前复权 `fq='pre'` 依赖 T 之后的所有除权事件，每次新除权都会改变所有历史价格，**不适合缓存**。

**缓存中需要同时存两份价格**：
- `{time}__hist_post`: 后复权价，用于收益率计算
- `{time}__current_raw`: 原始价（`fq=None`），用于现价/涨跌停检测

### 3.3 缓存键命名规范

格式：`{HH:MM}__{function_name}__{data_type}`

**同一函数在不同时间点调用时，必须用时间前缀区分**。例如 `get_tiny_index()` 在 09:45 和 14:57 都被调用，缓存键分别是 `09:45__tiny_index_1d` 和 `14:57__tiny_index_1d`。

```python
# 错误：缺少时间前缀，sweep 模式会返回错误时间点的数据
cache_key = 'tiny_index_1d'  # ❌

# 正确：带时间前缀
tp = str(context.current_dt)[-8:]
cache_key = '{}__tiny_index_1d'.format(tp[:5])  # ✅
```

### 3.4 参数无关 vs 参数相关（关键）

缓存设计必须区分两类数据：

**参数无关（缓存一次，所有参数组合复用）**：
- 股票池列表、价格数据、基本面数据、成交量、行业分类、涨跌停价
- 这些是原始市场数据，不受策略参数影响

**参数相关（从缓存重算，不缓存结果）**：
- 信号评分、择时判断、选股排名、买卖决策
- 这些是原始数据的计算结果，不同参数会产生不同结果

**设计原则**：只缓存参数无关的原始数据。参数相关的计算在 sweep 时从缓存的原始数据重算。

示例：如果选股逻辑是"选市值最小的 N 只"且 N 是可调参数：
- ✅ 缓存所有候选股的市值数据（参数无关）
- ❌ 不缓存"最终选中的 N 只股票"（参数相关，N 变了结果就变了）

### 3.5 累积数据（meta）

跨日累积数据单独存储在 `meta.pkl.gz`：

```python
meta = {
    'cumulative_data_1': DataFrame,  # 策略特定的跨日数据
    'event_log': list,               # 事件记录
    ...
}
```

**Sweep 模式下累积数据只读**：sweep 模式只能从 meta 读取数据，绝对不能 `append()` 或修改累积数据。否则多次 sweep 会导致数据膨胀。

```python
# ❌ sweep 模式下追加累积数据（会导致重复膨胀）
if CACHE_MODE != 'live':
    g.event_log.append(new_event)

# ✅ 正确：只在 collect/live 模式下追加
if CACHE_MODE != 'sweep':
    g.event_log.append(new_event)
```

### 3.6 断点续传

```python
def initialize(context):
    if CACHE_MODE in ('sweep', 'collect'):
        meta = load_meta_cache()
        if meta:
            # 恢复累积数据
            g.cumulative_data = meta['cumulative_data_1']
            ...

def trade(context):
    if current_time == first_time_of_day:
        if CACHE_MODE == 'collect':
            existing = load_daily_cache(date_str)
            if existing is not None:
                g._skip_today = True  # 跳过今日
                return

def after_trading_end(context):
    if CACHE_MODE == 'collect':
        if getattr(g, '_skip_today', False):
            return  # 已有缓存，不重复保存
        save_meta_cache(...)       # 先保存 meta
        save_daily_cache(...)       # 再保存每日缓存
```

**保存顺序：meta 先于 daily**。如果 daily 保存成功但 meta 保存失败，累积数据会不完整。

**CP-3.1** ✅ 缓存键规范无冲突 | **CP-3.2** ✅ sweep/collect 拦截完整 | **CP-3.3** ✅ meta 覆盖所有累积数据 | **CP-3.4** ✅ 断点续传正确

---

## 阶段四：Collect 模式运行

### 4.1 运行前检查

- [ ] `CACHE_MODE = 'collect'`
- [ ] `PARAMS` 使用默认值或已知基准值
- [ ] 回测区间覆盖目标
- [ ] 回测频率正确（通常 `minute`）
- [ ] 初始资金合理（通常 1,000,000）

### 4.2 通过 jqcli 提交

```bash
jqcli strategy edit {algo_id} --file strategy.py
jqcli backtest run {algo_id} --start {start} --end {end} --capital {capital} --freq minute
```

### 4.3 聚宽平台限制

| 限制 | 数值 | 影响 |
|------|------|------|
| 最大并行回测 | 10 个 | 并发扫描脚本需控制并发数 |
| 单次回测时长 | ~5 小时（分钟频） | collect 长区间回测可能超时 |
| 免费积分 | 每日有限 | 积分不足时等待次日或购买 |
| 研究环境存储 | ~5GB | 5年缓存约 1.5-2.5GB，够用 |

### 4.4 监控

轮询回测状态直到 `done` 或 `failed`。collect 完成后验证缓存文件数量等于交易日数量。

**CP-4.1** ✅ 配置检查通过 | **CP-4.2** ✅ 回测运行中 | **CP-4.3** ✅ 缓存完整

---

## 阶段五：择时有效性验证

### 5.1 择时条件开关验证

逐个关闭择时条件（设 `enabled=False`），用 sweep 跑回测，记录夏普变化。每个条件的贡献度 = 基准夏普 - 关闭后夏普。

```python
# 验证流程
base_result = run_sweep(all_enabled=True)  # 基准

for condition in timing_conditions:
    PARAMS[f'{condition}_enabled'] = False
    result = run_sweep(PARAMS)
    contribution = base_result['sharpe'] - result['sharpe']
    PARAMS[f'{condition}_enabled'] = True  # 恢复
```

**分析维度**：夏普贡献、回撤控制效果、条件间冗余检测。

### 5.2 参数敏感性

单边扫描核心参数，绘制参数值 vs 夏普曲线。判断是否单调/单峰。

```python
# 每个参数 M 个取值，共 N 个参数
for param_name in core_params:
    for value in param_values:
        PARAMS[param_name] = value
        run_sweep(PARAMS)
```

**CP-5.1** ✅ 择时条件贡献量化 | **CP-5.2** ✅ 敏感性曲线已绘制

---

## 阶段六：参数寻优

### 6.1 搜索空间

基于阶段五的敏感性分析确定搜索范围。总组合数 < 200。

### 6.2 Sweep 并发扫描

```python
MAX_CONCURRENT = 10  # 聚宽限制
POLL_INTERVAL = 15

# 1. 修改策略参数 → 2. 上传代码 → 3. 提交 sweep 回测
# 4. 轮询等待 → 5. 提取指标 → 6. 保存结果
# 7. 补充新回测到并发上限
```

关键：sweep 回测每次只需 3-10 分钟（vs collect 的 3-5 小时）。

### 6.3 结果排序

排序指标：夏普（主）→ 年化收益（次）→ 回撤约束（< 30%）。

**CP-6.1** ✅ 搜索空间预筛选 | **CP-6.2** ✅ 并发脚本就绪 | **CP-6.3** ✅ 最优参数不在边界

---

## 阶段七：稳健性检验

| 检验项 | 方法 | 通过标准 |
|--------|------|---------|
| 样本外验证 | 2017-2022 优化，2023-2026 验证 | 样本外夏普 ≥ 样本内 × 0.7 |
| 参数扰动 | 最优参数 ±20% 范围扰动 | 夏普下降 < 20% |
| 极端行情 | 单独回测 2018熊市/2020疫情/2021抱团瓦解 | 回撤 < 40% |

**CP-7.1** ✅ 样本外无衰减 | **CP-7.2** ✅ 参数平坦 | **CP-7.3** ✅ 极端抗跌

---

## 阶段八：报告撰写

报告结构：策略概述 → 重构过程 → 因子有效性 → 参数寻优 → 稳健性 → 风险提示。

必备图表（≥3 个）：收益曲线对比、参数敏感性热力图、IC 时间序列图、回撤分布图、择时贡献度条形图。

末尾必须含合规风险提示。

**CP-8.1** ✅ 图表齐全 | **CP-8.2** ✅ 含合规声明

---

## 常见陷阱

| 陷阱 | 规避 |
|------|------|
| 缓存键冲突（同一函数多时间点） | 使用 `{HH:MM}__` 时间前缀 |
| sweep 污染累积数据 | sweep 模式只读，不 append |
| meta 保存顺序错误 | meta 先于 daily 保存 |
| collect 覆盖已有缓存 | 断点续传：先检查，已存在则跳过 |
| `hasattr(g, g.csv_name)` bug | 改为检查 `hasattr(g, 'data') and not g.data.empty` |
| 并发超过 10 个 | 捕获错误，等待槽位释放，不标记失败 |
| 前复权数据不稳定 | 一律使用后复权 `fq='post'` |
