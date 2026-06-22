---
name: jq-full-optimizer
description: 聚宽策略全流程优化器。涵盖策略解构、架构重构、缓存层设计（collect/sweep/live 三模式）、择时条件开发、参数寻优、稳健性检验到报告撰写的完整 8 阶段 SOP。适用于所有聚宽量化策略。Trigger when user wants to optimize, refactor, or add cache/sweep to a JoinQuant strategy.
---

# 聚宽策略全流程优化器

当用户输入 `/jq-full-optimizer` 时，按以下 8 阶段工作流推进。每个阶段末尾有检查点（CP），必须通过才能进入下一阶段。**通过后立即生成阶段报告**，作为交付物和断点恢复的可视化标记。

> 详细参考文档：[SOP 正文](references/SOP_v1.md) | [流程图](references/SOP_流程图.md)
> 本 Skill 适用于**所有聚宽量化策略**，不绑定任何特定策略。

---

## 全局规范

### Workspace 文件管理

所有过程产物统一保存到策略文件同目录下的 `jq_optimizer_workspace/` 子目录，由 `manifest.json` 总索引管理。

```
{策略文件同目录}/jq_optimizer_workspace/
├── manifest.json                     # 📋 总索引（所有文件的目录卡）
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
    └── sweep_scan.py
```

**manifest.json 格式**：

```json
{
  "strategy_name": "策略名称",
  "strategy_file": "策略文件路径",
  "algo_id": "聚宽策略ID",
  "created_at": "2026-06-13T10:00:00",
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
    {"path": "phase6_sweep/sweep_results.json", "phase": 6, "type": "result", "description": "参数扫描结果"}
  ]
}
```

**文件管理规则**：
- 阶段报告命名：`phase{N}_report.md`（1-3 在根目录，4-8 在子目录）
- 结果文件命名：`{experiment_type}_results.json`
- 断点文件命名：`{experiment_type}_checkpoint.json`
- 脚本存档命名：`scripts/{purpose}_scan.py`
- 每次新增文件时同步更新 `manifest.json`

### 断点恢复机制

当会话中断或用户需要恢复进度时：

1. **读取 `manifest.json`**：确认 `current_phase` 和各阶段 `status`
2. **读取最近完成的阶段报告**：了解上一阶段的产出和关键数据
3. **检查当前阶段是否已有中间产物**：
   - 有 `*_results.json` → 统计已完成数，从断点续跑
   - 有 `*_checkpoint.json` → 恢复 active/pending/remaining 状态
   - 什么都没有 → 从头开始当前阶段
4. **向用户报告恢复状态**，确认后继续

### 阶段退出条件

并非所有策略都需要经历全部 8 个阶段。以下情况可跳过：

| 阶段 | 可跳过条件 | 跳过时操作 |
|------|-----------|-----------|
| 阶段一 | 无（必须执行） | — |
| 阶段二 | 策略已有 PARAMS 字典 + 函数解耦 | 报告中标注"已满足，跳过" |
| 阶段三 | 策略已有 collect/sweep 缓存层 | 报告中标注"已满足，跳过" |
| 阶段四 | 缓存文件已存在且完整 | 验证完整性后跳过 |
| 阶段五 | 用户明确不需要择时验证 | 跳过但记录原因 |
| 阶段六 | 用户明确不需要参数寻优 | 跳过但记录原因 |
| 阶段七 | 用户明确不需要稳健性检验 | 跳过但记录原因 |
| 阶段八 | 无（必须执行） | — |

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

### Step 4a：确认策略部署方式

**必须先询问主人**：这个策略是上传到聚宽**现有的策略**（提供链接或 algo_id），还是**新建一个回测策略**？

| 场景 | 做法 | 风险 |
|------|------|------|
| 已有 algo_id 的策略 | `jqcli strategy edit {algo_id} --file strategy.py` + 4.2a read-back 验证 | 覆盖该 algo_id 下的旧代码 + 历史回测 |
| 全新策略 | 主人先在聚宽网页 https://www.joinquant.com/algorithm/index 手动新建 → 拿到 algo_id → 再用 edit | 需要主人额外操作一次 |
| 复用别人策略 | 同"全新策略"流程，但要在 manifest.json 标注来源 + 脱敏处理 | 版权/凭据风险 |

**询问模板**（直接发给主人）：

> 主人，请确认这个策略怎么部署？
> 1. **上传到现有策略**（请提供聚宽 algo_id 或策略链接，例如 `https://www.joinquant.com/algorithm/index/edit?algorithmId=xxxx`）
> 2. **新建一个回测策略**（我会引导您在聚宽网页手动创建后取 algo_id）
> 注意：选 1 会覆盖该 algo_id 下的现有代码，请确认是无用版本

**CP-4a** ✅ 主人明确选择"上传现有"或"新建"，并提供对应 algo_id 或已新建完成

### Step 5：初始化 Workspace

在策略文件同目录下创建 `jq_optimizer_workspace/` 目录和 `manifest.json`：

```python
workspace_dir = os.path.join(os.path.dirname(strategy_file), 'jq_optimizer_workspace')
os.makedirs(workspace_dir, exist_ok=True)
manifest = {
    'strategy_name': os.path.basename(strategy_file),
    'strategy_file': strategy_file,
    'algo_id': algo_id,
    'created_at': current_time,
    'current_phase': 0,
    'phases': {},
    'artifacts': []
}
json.dump(manifest, open(os.path.join(workspace_dir, 'manifest.json'), 'w'), indent=2)
```

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

**进阶要求（推荐）**：除上面的功能分解外，再画一张 **3 层架构图**——这是借鉴 quant-auto-research 的核心骨架：

```
Layer 1 大盘择时（市场状态 → 是否交易）
   输入：沪深300历史价 + 波动率
   输出：market_regime ∈ {long, short}
   模块：TimingJudge

Layer 2 质量过滤（股票池 → 候选股）
   输入：全 A 股 + 财务数据
   输出：quality_stocks（每日缓存）
   模块：QualityFilter

Layer 3 组合优化（候选股 + 因子 → 权重）
   输入：候选股 + 因子值
   输出：目标权重矩阵
   模块：FactorPortfolioOptimization

跨层 止损（持仓监控 → 卖出信号）
   输入：当前持仓 + 实时价
   输出：止损单
   模块：StopManager
```

**为什么强调 3 层架构**：
- 每层可以**独立运行、独立验证**：能单独跑消融实验、看每一层到底贡献多少
- 每层可以**独立替换**：择时模块写坏了可以单独换，不动选股和组合优化
- 3 层之间是**单向数据流**：Layer 1 输出 → Layer 2 输入 → Layer 3 输入，依赖关系一目了然

**判断准则**：如果你的策略能清楚画出这 3 层 + 1 跨层（止损），说明结构清晰；画不出来说明耦合严重，需要先重构再优化。

### 1.4 识别可调参数

输出参数表：

```
# | 参数 | 含义 | 当前值 | 合理范围 | 类型
1 | lookback | 均线窗口 | 20 | [5, 120] | int
2 | threshold | 信号阈值 | 0.1 | [0.01, 0.5] | float
...
```

**CP-1.1** ✅ 所有 API 调用已分类 | **CP-1.2** ✅ 模块输入输出清晰 | **CP-1.3** ✅ 参数表完整

> **恢复指令**：读取 `phase1_deconstruct.md`，检查 API 清单、模块图、参数表是否完整。

**阶段报告** → 生成 `jq_optimizer_workspace/phase1_deconstruct.md`

---

## 阶段二：架构重构

### 2.1 PARAMS 字典

将所有可调参数集中到一个 `PARAMS` 字典：

```python
PARAMS = {
    # 择时开关
    '{condition_name}_enabled': True,
    # 择时参数
    '{param_name}': default_value,  # [min, max]
    # 选股参数
    '{param_name}': default_value,
    # 风控参数
    '{param_name}': default_value,
}
```

在 `initialize()` 中：`g.params = PARAMS.copy()`

**进阶做法（推荐）**：除 PARAMS 字典外，额外产出 `params_schema.json`，把参数定义从代码里拆出来。

理由：改参数不用动策略文件 → 跳过聚宽冷启动审核；sweep 脚本读 JSON 即可，不用 ast 解析 .py。

格式（直接复用 quant-auto-research 的 schema）：

```json
[
  {
    "name": "stock_num",
    "display_name": "持仓数量",
    "default_value": 30,
    "type": "integer",
    "min": 10, "max": 50, "step": 5,
    "group": "持仓",
    "description": "组合持仓股票数量"
  },
  {
    "name": "stop_ratio",
    "display_name": "止损比例",
    "default_value": 0.1,
    "type": "float",
    "min": 0.05, "max": 0.2, "step": 0.01,
    "group": "止损",
    "description": "价格跌破最高点 N% 止损"
  }
]
```

**强制字段**：`name / default_value / type / min / max / step / group / description`
**type 可选值**：`integer / float / bool / categorical`
**group 分组建议**：`["择时", "选股", "持仓", "止损", "因子协方差"]`
**回填策略**：阶段六 sweep 脚本 `import json; schema = json.load(open('params_schema.json'))`，遍历 schema 改参数后注入策略。

### 2.2 择时开关

每个择时条件设计独立 `enabled` 开关，命名规范 `{condition_name}_enabled`。

### 2.3 函数解耦

目标：主交易函数不超过 30 行。每个择时条件和选股步骤为独立函数。

**CP-2.1** ✅ 无硬编码参数 | **CP-2.2** ✅ 每个条件可独立开关 | **CP-2.3** ✅ 主交易函数 ≤ 30 行

> **恢复指令**：读取 `phase2_refactor.md`，确认 PARAMS 字典、开关列表、函数解构图。
> **退出条件**：如果策略已有 PARAMS + 函数解耦，报告中标注"已满足"并跳过。

**阶段报告** → 生成 `jq_optimizer_workspace/phase2_refactor.md`

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

**同一函数在不同时间点调用时，必须用时间前缀区分**。

### 3.4 参数无关 vs 参数相关（关键）

**参数无关（缓存一次，所有参数组合复用）**：
- 股票池列表、价格数据、基本面数据、成交量、行业分类、涨跌停价

**参数相关（从缓存重算，不缓存结果）**：
- 信号评分、择时判断、选股排名、买卖决策

**设计原则**：只缓存参数无关的原始数据。参数相关的计算在 sweep 时从缓存的原始数据重算。

### 3.5 累积数据（meta）

跨日累积数据单独存储在 `meta.pkl.gz`。

**Sweep 模式下累积数据只读**：sweep 模式只能从 meta 读取数据，绝对不能 `append()` 或修改累积数据。

### 3.6 断点续传

```python
def initialize(context):
    if CACHE_MODE in ('sweep', 'collect'):
        meta = load_meta_cache()
        if meta:
            # 恢复累积数据
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
            return
        save_meta_cache(...)       # 先保存 meta
        save_daily_cache(...)       # 再保存每日缓存
```

**保存顺序：meta 先于 daily**。

**CP-3.1** ✅ 缓存键规范无冲突 | **CP-3.2** ✅ sweep/collect 拦截完整 | **CP-3.3** ✅ meta 覆盖所有累积数据 | **CP-3.4** ✅ 断点续传正确

> **恢复指令**：读取 `phase3_cache_design.md`，确认缓存键列表、拦截点列表、meta 数据结构。
> **退出条件**：如果策略已有 collect/sweep 缓存层，验证完整性后跳过。

**阶段报告** → 生成 `jq_optimizer_workspace/phase3_cache_design.md`

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
    """上传策略代码并验证生效"""
    # 1. 上传
    html = client.get_text('/algorithm/index/edit', params={'algorithmId': strategy_id})
    detail = parse_strategy_edit_html(html, requested_id=strategy_id)
    payload = dict(detail['_form'])
    payload['algorithm[algorithmId]'] = str(detail['save_id'])
    payload['algorithm[code]'] = base64.b64encode(code.encode('utf-8')).decode('ascii')
    payload['encrType'] = 'base64'
    client.post('/algorithm/index/save', data=payload)  # 其余 payload 字段略

    # 2. 验证（read-back）
    html2 = client.get_text('/algorithm/index/edit', params={'algorithmId': strategy_id})
    detail2 = parse_strategy_edit_html(html2, requested_id=strategy_id)
    saved_code = base64.b64decode(detail2['_form']['algorithm[code]']).decode('utf-8')

    # 3. 比对关键行
    uploaded_lines = code.strip().split('\n')[:20]
    saved_lines = saved_code.strip().split('\n')[:20]
    if uploaded_lines != saved_lines:
        raise ValueError("上传验证失败：代码不匹配！")

    return strategy_id  # 用原始 ID
```

**CP-4.2a** ✅ 上传代码已验证（read-back 通过）

### 4.3 聚宽平台限制

| 限制 | 数值 | 影响 |
|------|------|------|
| 最大并行回测 | 10 个 | 并发扫描脚本需控制并发数 |
| 单次回测时长 | ~5 小时（分钟频） | collect 长区间回测可能超时 |
| 免费积分 | 每日有限 | 积分不足时等待次日或购买 |
| 研究环境存储 | ~5GB | 5年缓存约 1.5-2.5GB，够用 |

### 4.4 监控

轮询回测状态直到 `done` 或 `failed`。collect 完成后验证缓存文件数量等于交易日数量。

**CP-4.1** ✅ 配置检查通过 | **CP-4.2** ✅ 回测运行中 | **CP-4.2a** ✅ 上传验证通过 | **CP-4.3** ✅ 缓存完整

> **恢复指令**：读取 `phase4_collect/phase4_report.md`，检查 cache_status.json 中的缓存文件数 vs 交易日数。
> **退出条件**：如果缓存文件已存在且完整（数量 == 交易日数），跳过。

**阶段报告** → 生成 `jq_optimizer_workspace/phase4_collect/phase4_report.md`

---

## 阶段五：择时有效性验证

### 5.0 择时条件开发子流程（可选）

> 当需要**新增或替换**一个择时条件时，在阶段五之前执行此子流程。如果只是验证现有条件，跳过此步骤。

#### 5.0.1 独立信号研究

- 编写独立研究脚本（不修改主策略）
- 在研究脚本中同时计算新旧信号，对比差异
- 标记关键极端时段的信号表现

#### 5.0.2 信号参数预筛选

- 用独立脚本进行粗粒度参数扫描（小范围）
- 确定参数大致合理区间，避免全量搜索

#### 5.0.3 集成到主策略

使用**集成清单**追踪所有修改点：

```markdown
## 集成清单

| # | 文件 | 行号 | 修改内容 | 状态 |
|---|------|------|---------|------|
| 1 | {strategy}.py | L{N} | 新增 `{condition}_enabled` 参数 | ⬜ |
| 2 | {strategy}.py | L{N} | 替换旧参数为新参数组 | ⬜ |
| 3 | {strategy}.py | L{N} | 新增 `{condition}()` 函数 | ⬜ |
| 4 | {strategy}.py | L{N} | 更新调用点引用 | ⬜ |
| ... | ... | ... | ... | ... |
```

#### 5.0.4 集成验证

- 修改后跑一次 sweep 回测，确认收益与独立脚本结果趋势一致
- 如果不一致 → 用集成清单逐项排查遗漏

#### 5.0.5 同步更新扫描脚本

如果策略有配套的 sweep 扫描脚本，同步更新其中的参数名和开关名。

### 5.1 择时条件开关验证（消融实验）

逐个关闭择时条件（设 `enabled=False`），用 sweep 跑回测，记录收益和夏普变化。

使用**标准化扫描脚本骨架**（见 SOP 附录 E），只需填写 CUSTOMIZE 区域：

```python
# CUSTOMIZE 区域示例
TASKS = [
    ('baseline', '基准(全开)', lambda code: code),
    ('close_{cond1}', '关闭{条件1}', lambda code: modify_param(code, '{cond1}_enabled', False)),
    ('close_{cond2}', '关闭{条件2}', lambda code: modify_param(code, '{cond2}_enabled', False)),
    ...
]
```

**并发控制**：`MAX_CONCURRENT = 8`（留 2 个槽位缓冲，聚宽限制 10 个并行）

每个条件的贡献度 = 基准收益 - 关闭后收益（负值越大越重要）。

**分析维度**：收益贡献、夏普贡献、回撤控制效果、条件间冗余检测。

### 5.2 参数敏感性

单边扫描核心参数，绘制参数值 vs 收益/夏普曲线。判断是否单调/单峰。

### 5.3 多周期并行训练（防单窗口过拟合）

**为什么必须有**：单一训练窗口过拟合风险极高。原作者自己的数据就证明了：

| 同一套参数 | 2012-2017 段 | 2016-2020 段 | 2017-2021 段 |
|-----------|-------------|-------------|-------------|
| Sharpe | +1.22 | +1.77 | -0.77 |
| 评价 | ✅ | ✅ | ❌ 崩了 |

只在 2016-2020 上跑出 +1.77 看起来很美，但同样的参数到 2017-2021 直接 -0.77。这是典型的**单窗口过拟合**。

**强制要求**：阶段六 sweep 时，**同时在 4 个错开的时间窗口上训练**。默认窗口（项目初始 2026 年起算，可滚动更新）：

| 训练周期 | 时间范围 | 交易日数 | 用途 |
|---------|---------|---------|------|
| W1 | 2012-01-01 → 2017-12-31 | ~1500 | 老牛市验证 |
| W2 | 2014-01-01 → 2019-12-31 | ~1500 | 中长期验证 |
| W3 | 2016-01-01 → 2020-12-31 | ~1222 | **主训练期** |
| W4 | 2017-01-01 → 2021-12-31 | ~1200 | 熊市/转折验证 |

**接受准则**：参数组合必须在 **≥3/4 周期**上 Sharpe 一致提升才接受；否则即便主训练期 W3 看起来好也**拒绝**。

**在 `params_schema.json` 里定义窗口**（参考 quant-auto-research 格式）：

```json
{
  "backtest_period": {
    "training_windows": [
      {"name": "W1", "start": "2012-01-01", "end": "2017-12-31"},
      {"name": "W2", "start": "2014-01-01", "end": "2019-12-31"},
      {"name": "W3", "start": "2016-01-01", "end": "2020-12-31", "is_primary": true},
      {"name": "W4", "start": "2017-01-01", "end": "2021-12-31"}
    ],
    "testing": {"start": "2021-01-01", "end": "2026-05-15"}
  }
}
```

**代价估算**（与 §6.1 Optuna 协调）：

| 阶段 | 单 trial | n_trials | 并发 | 总耗时 |
|------|---------|---------|------|--------|
| 单窗口 sweep | 7.5 min | 500 | 4 | ≈ 16 h |
| 4 窗口 sweep（强制）| 30 min | 500 | 4 | ≈ 62.5 h ≈ **2.6 天** |
| 4 窗口 + TPE 500 trials（实际）| 30 min | 500 | 4 | ≈ **7-10 天**（含失败重跑、缓存 miss、人工审查） |

**预算提示**：TPE 默认 500 trials × 4 窗口 = 62.5 小时纯计算时间。叠加失败重跑、collect 缓存 miss、人工审查 ≈ **7-10 天实际工作日**。

**降级选项**（预算紧时）：
- n_trials=200 → ≈ 1.2 天（仍能用 TPE）
- n_trials=50 → ≈ 7 h（仅作 debug 验证）
- 4 窗口关到 1 窗口 → 7.5 min/trial（**禁用**：丧失 §5.3 多窗口防过拟合核心机制）

**回退规则**：用户明确说"我只要主训练期"时，可以关闭多周期训练，但必须在阶段五报告里标注 `multi_window_disabled: true` 并说明原因。

**CP-5.1** ✅ 择时条件贡献量化 | **CP-5.2** ✅ 敏感性曲线已绘制

> **恢复指令**：读取 `phase5_validation/phase5_report.md`，检查 ablation_results.json 和 sensitivity_results.json 是否完整。
> **退出条件**：用户明确不需要择时验证时跳过，记录原因。

**阶段报告** → 生成 `jq_optimizer_workspace/phase5_validation/phase5_report.md`

---

## 阶段六：参数寻优

### 6.1 搜索空间与 HPO 方法选择

**核心原则：参数优化是 HPO（超参数优化）问题，不只是枚举问题。** 11 个参数 × 5 step = 5^11 = 4883 万组合；11 参数 × 2 step × 多周期 × 多标的 = 226 亿组合（P0-3 漏洞）。Grid search 在 7.5 min/次 × 8 并发下需要 4 万年，必须用 HPO 框架。

**方法选择决策树**（按预算/维度数选）：

| 搜索空间 | 推荐方法 | 预算（trials） | 适用场景 |
|---------|---------|--------------|---------|
| < 500 组合 | 全量 Grid | 1 次跑完 | 阶段五敏感性已缩到 1-2 参数 |
| 500 - 5 万 | TPE（贝叶斯） | 200-1000 | **默认推荐**：维度 ≤ 8 性价比最高 |
| 5 万 - 100 万 | Hyperband / BOHB | 500-2000 | 预算紧、要 early stopping |
| > 100 万 | 进化策略 / 异步 TPE | 1000+ | 高维（≥ 12 参数）且预算充裕 |

**推荐实现：Optuna + TPE**

```python
import optuna
from optuna.samplers import TPESampler

def objective(trial: optuna.Trial) -> float:
    params = {
        "stop_ratio": trial.suggest_float("stop_ratio", 0.05, 0.20, step=0.01),
        "hold_days":  trial.suggest_int("hold_days", 3, 15),
    }
    sharpe, aic_bic = submit_sweep_backtest(params)
    return aic_bic

study = optuna.create_study(
    direction="maximize",
    sampler=TPESampler(seed=42, n_startup_trials=20),
)
study.optimize(objective, n_trials=500, n_jobs=4)
```

**为什么用 TPE 不用 Grid**：
- 8 维 × 5 step = 39 万组合，Grid 跑 4.5 万小时，TPE 用 500 trials 即可逼近最优
- TPE 自适应：第 100 次 trial 时已经知道调紧止损有用、放宽窗口没用，会集中预算到有希望的维度
- 原 quant-auto-research 的 6 轮手动调参结果中 5/6 用了相同参数 = 人工每轮微调 1-2 个参数也只在小范围试探，TPE 自适应采样会比这覆盖更广

**关键约束（与 sweep 协调）**：
1. **n_trials ≤ sweep_max / 8**（避免单策略霸占 sweep 通道）
2. **n_jobs ≤ 4**（sweep 上限 8，预留 4 给基线/重试）
3. **断点续跑**：Optuna study 持久化到 SQLite (study.db)，重启自动接续
4. **随机种子固定**：seed=42 保证 500 trials 跑完的最优可复现

**回退到 Grid 的合法场景**：
- 阶段五 ablation 证明只剩 1-2 个有效参数（其余 9 个不敏感）→ Grid 总组合 < 500
- 调试 / 验证 sweep 脚本本身 → 手动指定 3-5 个点

**禁止**：
- 维度 ≥ 5 还用全量 Grid
- 不写 n_trials 让 Optuna 跑到 sweep 排队炸掉

**CP-6.1** HPO 方法已选型 | **CP-6.1b** TPE sampler + 种子固定 | **CP-6.1c** 并发预算协调

### 6.2 Sweep 并发扫描

使用**标准化扫描脚本骨架**（见 SOP 附录 E），核心流程：

```
1. 加载已有结果（断点续跑）
2. 修改策略参数 → 上传（含验证）→ 提交 sweep 回测
3. 轮询等待 → 提取指标（含 None 防御）→ 保存结果
4. 补充新回测到并发上限（MAX_CONCURRENT = 8）
```

关键：sweep 回测每次只需 3-10 分钟（vs collect 的 3-5 小时）。

**聚宽并发限制处理**：
- 提交前检查当前运行中回测数 < 8
- 遇到"超过 10 个"错误 → **不标记失败**，放回队列等待重试
- 使用指数退避：30s → 60s → 120s → 300s

### 6.3 结果排序

排序指标：**AIC/BIC 评分（主）** → 夏普（次）→ 年化收益（再次）→ 回撤约束（< 30%）。

**AIC/BIC 评分公式**（借鉴 quant-auto-research，核心防过拟合机制，**多窗口版本**）：

```python
import math
from typing import Literal

def aic_bic_score_multi(
    sharpes: list[float],
    params_count: int,
    training_days: int = 1222,
    agg: Literal['min', 'mean', 'median'] = 'min',
) -> float:
    """多窗口 AIC/BIC 评分（与 §5.3 的 4 窗口配套）。

    大白话：你改 1 个参数但 4 窗口里最差那个 Sharpe 只涨了 5 分 < 7.11 扣分 → 不及格，拒绝。
    改 3 个参数 4 窗口最差那个 Sharpe 涨 20 分 → 扣 21.33 分 → 还是负分 → 拒绝。
    
    关键：默认 agg='min'（用最差窗口的 Sharpe 算扣分），让 §5.3 强制 ≥3/4 周期
    一致提升的接受准则真正进入评分。如果用 mean，主训练期 W3 虚高会拉高均值，
    掩盖 W4 熊市崩盘——那就又退化成单窗口过拟合。
    """
    if not sharpes:
        raise ValueError('sharpes 不能为空')
    if agg == 'min':
        worst = min(sharpes)
    elif agg == 'mean':
        worst = sum(sharpes) / len(sharpes)
    elif agg == 'median':
        worst = sorted(sharpes)[len(sharpes) // 2]
    else:
        raise ValueError(f'未知聚合方式: {agg}')
    penalty = params_count * math.log(training_days)  # 默认训练期 ≈ 5 年，log(1222) ≈ 7.11
    return worst - penalty

# 单窗口别名（向后兼容 quant-auto-research 单调参代码）
aic_bic_score = aic_bic_score_multi  # 单窗口调用传 [sharpe] 即可
```

**强制要求**：
1. sweep 脚本每跑完一组参数，**两个指标都必须保存**：`sharpe` 和 `aic_bic_score`
2. 阶段六报告 `phase6_report.md` 必须把两列都列出来，让人类能一眼看到"夏普涨了但 AIC/BIC 跌了"的过拟合信号
3. `params_count` = 本轮 sweep **实际改动**的参数数量（不是策略总参数数）
4. `training_days` 默认 1222（对应 2016-2020 主训练期），可在 `params_schema.json` 的 `backtest_period.training` 字段自动推算
5. AIC/BIC 评分为负时，必须在报告里打 ⚠️ 警告（提示可能过拟合）

**回退规则**：用户明确说"我就要看原始夏普，不用扣分"时，可以关闭 AIC/BIC 排序，但必须在阶段六报告里标注 `aic_bic_disabled: true` 并说明原因。

### 6.4 结果记录格式（JSONL 追加式）

**强制要求**：阶段六 sweep 结果除 `sweep_results.json` 外，**同步追加一行**到 `jq_optimizer_workspace/phase6_sweep/results.jsonl`。

**为什么用 JSONL 而不是 JSON 数组**：
- 追加写一行 ≈ 毫秒级；改 JSON 数组要重写整个文件
- `tail -1 results.jsonl` 拿最新轮，断点恢复超快
- `grep '"status": "improved"'` 命令行直接过滤
- AI 复盘时一行就是一轮决策，自然语言字段 `rationale` 直接读

**每行字段**（直接复用 quant-auto-research 的 schema）：

```json
{"round": 1, "timestamp": "2026-06-22T10:30:00", "git_commit": "abc1234567", "params_changed": [{"name": "stop_ratio", "before": 0.1, "after": 0.15}], "params_count": 1, "sharpe": 1.13, "aic_bic_score": -5.98, "max_drawdown": 0.18, "annual_return": 0.21, "status": "improved", "rationale": "调紧止损，减少单次损失"}
```

**强制字段**：`round / timestamp / git_commit / params_changed / params_count / sharpe / aic_bic_score / status`
**status 取值**：`baseline / improved / degraded / rejected`
**git_commit 字段**：必须用 `git rev-parse HEAD` 拿真实 hash 写入，不要手填（quant-auto-research 的 jsonl 这里就有假 hash，`git checkout` 会失败）
**rationale 字段**：人类写的自然语言，解释为什么改这个参数，AI 复盘时直接读

**sweep 脚本骨架**：

```python
import json, subprocess
from pathlib import Path

def append_round(result: dict, jsonl_path: Path = Path("results.jsonl")) -> None:
    """每跑完一组参数就追加一行。"""
    result["git_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
    result["timestamp"] = subprocess.check_output(["date", "-Iseconds"]).decode().strip()
    with jsonl_path.open("a") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")
```

**快速查询命令**（给人类用）：

```bash
# 看总轮数
wc -l phase6_sweep/results.jsonl

# 看最新一轮
tail -1 phase6_sweep/results.jsonl | jq .

# 只看成功的轮
grep '"status": "improved"' phase6_sweep/results.jsonl | jq .
```

### 6.5 实验生命周期（4 停止条件状态机）

把"什么情况算优化结束"明确写成状态机，避免优化器死循环或人工手动监控。

借鉴 quant-auto-research 的 4 个停止条件，改写成可机读的状态机：

```python
from dataclasses import dataclass
from enum import Enum

class StopReason(Enum):
    RUNNING = "running"                # 未结束
    TARGET_SHARPE = "target_sharpe"    # 达标
    NO_IMPROVEMENT = "no_improvement"  # 连续无提升
    SPACE_EXHAUSTED = "space_exhausted"  # 搜索空间耗尽
    MANUAL = "manual"                  # 人工干预

@dataclass
class ExperimentState:
    target_sharpe: float = 2.0
    consecutive_no_improvement_limit: int = 3
    max_rounds: int = 100

    consecutive_no_improvement_count: int = 0
    current_round: int = 0

    def check_stop(self, current_sharpe: float, history: list[float]) -> tuple[bool, StopReason]:
        # 1. Sharpe 达标
        if current_sharpe >= self.target_sharpe:
            return True, StopReason.TARGET_SHARPE

        # 2. 连续 N 轮 AIC/BIC 无提升
        if len(history) >= self.consecutive_no_improvement_limit:
            recent = history[-self.consecutive_no_improvement_limit:]
            if max(recent) == min(recent):  # 完全无提升
                return True, StopReason.NO_IMPROVEMENT

        # 3. 参数空间耗尽
        if self.current_round >= self.max_rounds:
            return True, StopReason.SPACE_EXHAUSTED

        return False, StopReason.RUNNING
```

**使用方式**：

```python
state = ExperimentState(target_sharpe=2.0, max_rounds=50)
history = []

for round_n in range(state.max_rounds):
    state.current_round = round_n
    score = aic_bic_score(sharpe=1.5, params_count=2)
    history.append(score)

    should_stop, reason = state.check_stop(score, history)
    append_round({"round": round_n, "score": score, "stop_reason": reason.value})

    if should_stop:
        log.info(f"实验结束: {reason.value}")
        break
```

**4 个停止条件**：

| # | 条件 | 默认值 | 何时调整 |
|---|------|-------|---------|
| 1 | 测试期 Sharpe 达标 | ≥ 2.0 | 用户在 `params_schema.json` 改 `target_sharpe` |
| 2 | 连续 N 轮 AIC/BIC 无提升 | N=3 | 用户在阶段六报告里写明 override |
| 3 | 参数空间耗尽（轮数上限） | max=100 | 同上 |
| 4 | 人工干预（用户主动 stop） | — | 用户随时可触发 |

**在 results.jsonl 里记录**：每轮追加 `stop_reason` 字段，让 AI 复盘时能直接看到"为什么这轮停了"。

**CP-6.1** ✅ HPO 方法已选型 | **CP-6.1b** ✅ TPE sampler + 种子固定 | **CP-6.1c** ✅ 并发预算协调（见 §6.1）；补充：最优参数不在边界（CP-6.1d，由 §6.4 jsonl + §6.5 状态机自动验证）

> **恢复指令**：读取 `phase6_sweep/phase6_report.md`，检查 sweep_results.json 中已完成数 / 总数。如有未完成的组合，用骨架脚本续跑。
> **退出条件**：用户明确不需要参数寻优时跳过，记录原因。

**阶段报告** → 生成 `jq_optimizer_workspace/phase6_sweep/phase6_report.md`

---

## 阶段七：稳健性检验

| 检验项 | 方法 | 通过标准 |
|--------|------|---------|
| 样本外验证 | 前半段优化，后半段验证 | 样本外夏普 ≥ 样本内 × 0.7 |
| 参数扰动 | 最优参数 ±20% 范围扰动 | 夏普下降 < 20% |
| 极端行情 | 单独回测典型极端区间（熊市/暴跌/反弹） | 回撤 < 40% |

**CP-7.1** ✅ 样本外无衰减 | **CP-7.2** ✅ 参数平坦 | **CP-7.3** ✅ 极端抗跌

> **恢复指令**：读取 `phase7_robustness/phase7_report.md`，检查 robustness_results.json。
> **退出条件**：用户明确不需要稳健性检验时跳过，记录原因。

**阶段报告** → 生成 `jq_optimizer_workspace/phase7_robustness/phase7_report.md`

---

## 阶段八：报告撰写

报告结构：策略概述 → 重构过程 → 择时有效性 → 参数寻优 → 稳健性 → 风险提示。

必备图表（≥3 个）：收益曲线对比、参数敏感性热力图、回撤分布图、择时贡献度条形图、分年度收益柱状图。

末尾必须含合规风险提示。

**CP-8.1** ✅ 图表齐全 | **CP-8.2** ✅ 含合规声明

> **恢复指令**：读取 `phase8_report/final_report.md`，检查报告完整性。

**阶段报告** → 生成 `jq_optimizer_workspace/phase8_report/final_report.md`（即最终交付物）

---

## 阶段报告模板

每个阶段的报告遵循统一格式：

```markdown
# 阶段 {N}：{阶段名称}

> 生成时间: {timestamp}
> 策略: {strategy_name}
> 状态: {completed | skipped}

## 关键产出

- 产出 1
- 产出 2
- ...

## 关键数据

| 指标 | 值 |
|------|-----|
| ... | ... |

## 遇到的问题

1. 问题描述 + 解决方案

## 下一阶段输入

- 阶段 {N+1} 需要的前置条件
- 关键参数/配置

## 产物文件

- `path/to/artifact1.json` — 用途说明
- `path/to/artifact2.json` — 用途说明
```

---

## 常见陷阱

| 陷阱 | 规避 |
|------|------|
| 缓存键冲突（同一函数多时间点） | 使用 `{HH:MM}__` 时间前缀 |
| sweep 污染累积数据 | sweep 模式只读，不 append |
| meta 保存顺序错误 | meta 先于 daily 保存 |
| collect 覆盖已有缓存 | 断点续传：先检查，已存在则跳过 |
| `hasattr(g, g.csv_name)` bug | 改为检查 `hasattr(g, 'data') and not g.data.empty` |
| **并发超过 10 个** | `MAX_CONCURRENT = 8`，捕获错误等待重试，**不标记失败** |
| 前复权数据不稳定 | 一律使用后复权 `fq='post'` |
| **jqcli 上传不生效** | 上传后 read-back 验证，用原始 strategy_id 提交回测 |
| **API 返回 None** | 格式化前做 None 检查，使用 `safe_fmt()` 统一格式化 |
