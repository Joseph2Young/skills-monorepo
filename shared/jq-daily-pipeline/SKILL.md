---
name: jq-daily-pipeline
description: 聚宽（JoinQuant）每日热门策略自动扫描 + IMA 入库流水线。每天定时拉取过去 24 小时内聚宽社区新发布的最热门策略 Top 3，跑 7.5 年（2019-01-01 至昨日）回测，筛选 0.8 < Sharpe <= 3.0 的策略，按聚宽策略审查分类提示词 v1.0 进行 12 大分类（趋势跟踪/均值回归/多因子选股/指数增强/事件驱动/资金流向/板块轮动/统计套利/技术形态/ML-AI 选股/波动率策略/成长股策略），按命名规则 `{年份}_{T编号}_{T简称}_{作者}_{标题核心}_s{Sharpe.2f}.md` 重命名后上传到腾讯 IMA 知识库。使用时机：用户希望搭建或运行聚宽策略自动扫描 + IMA 入库流水线、跨电脑移植该工作流、或调整阈值/命名规则/调度时间。
metadata:
  short-description: 聚宽策略每日扫描 + IMA 自动入库
---

# 聚宽每日策略扫描 + IMA 入库

## 跨 Agent 通用

本 skill 设计为可在多种 AI Agent 中运行（不绑定特定平台）：

| Agent | 支持方式 |
|---|---|
| **Codex** | 通过 `~/.codex/skills/jq-daily-pipeline/` 加载，或在「已安排任务」面板配置定时 |
| **Claude Code** | 加载为 skill，或用 cron 触发 |
| **Cursor** | 作为项目级 skill 加载，手动或 IDE 调度触发 |
| **通用 CLI** | 直接 `bash run_daily.sh`，配合 cron/launchd/GitHub Actions |
| **其他** | 见 `references/agent_compatibility.md` |

## 快速开始

完整流水线由 6 步组成，按顺序执行：

```
1. step1_filter.py         拉 30 页 → 过去 24h 窗口 → 名称去重 → Top 3
2. step2_ima_dedup.py      按年度查重 IMA → 过滤已入库
3. step3_clone.py          克隆 Top 3 + 拉策略代码
4. step4_backtest.py       跑 2019-01-01 ~ T-1 回测
5. step5_review_build.py   AI 审查 + 生成 markdown (阈值 0.8 < Sharpe <= 3.0)
6. step6_upload.py         上传到 IMA 当年文件夹
```

主入口 `run_daily.sh` 串起所有步骤。

## 前置条件

- `jqcli` 已安装并已登录聚宽（`jqcli auth status` 须显示"已配置"）；本地为 fork editable 安装（`聚宽策略研究/jqcli`，conda quantenv），**上游 https://github.com/breakhearts/jqcli.git 是别人的仓库，仅作拉取更新源，不要往它提交**
- 腾讯 IMA OpenAPI 凭证：Client ID + API Key（在 https://ima.qq.com/agent-interface 申请）
- IMA 凭证存到 `~/.config/ima/client_id` 和 `~/.config/ima/api_key`（每行一个值）
- Python 3.9+，依赖 `requests` 库

## 关键资源

| 文件 | 用途 |
|---|---|
| `scripts/run_daily.sh` | 主入口，依次跑 6 步 |
| `scripts/ima_api.py` | IMA 客户端抽象（connector 优先 + 降级） |
| `scripts/step1_filter.py` | 拉候选 + 24h 窗口 + 去重 |
| `scripts/step2_ima_dedup.py` | IMA 年度查重 |
| `scripts/step3_clone.py` | 克隆策略 + 拉代码 |
| `scripts/step4_backtest.py` | 跑回测 + 取 Sharpe |
| `scripts/step5_review_build.py` | AI 审查 + 生成 markdown |
| `scripts/step6_upload.py` | 上传 IMA |
| `references/classification.md` | 聚宽策略审查分类提示词 v1.0 |
| `references/parameters.md` | 关键参数表（阈值/命名/调度） |
| `references/setup.md` | 跨电脑移植清单 |
| `references/connectors.md` | IMA connector 检测与降级说明 |
| `references/agent_compatibility.md` | 各种 Agent 的接入方式 |
| `references/agent_scheduled_task.md` | 主流 Agent 的定时任务配置模板 |

## 关键参数

| 参数 | 取值 |
|---|---|
| 触发时间 | 每天 09:00（可改） |
| 时间窗口 | 过去 24 小时 |
| 每天克隆 | 3 个（Top by view_count） |
| 名称/代码去重阈值 | 80% |
| **Sharpe 阈值** | **0.8 < s <= 3.0** (下限不带等号, 上限带等号) |
| 回测窗口 | 2019-01-01 ~ T-1 (7.5 年) |
| 入库查重 | 按年度 |
| **命名格式** | **`{年份}_{T编号}_{T简称}_{作者}_{标题核心}_s{Sharpe.2f}.md`** |
| 文件名总长度上限 | 80 字符（含 `.md` 后缀），超阈值时告警 |

### 命名格式说明 (主人规则 2026-07-29)

```
{year}_{Tcode}_{Tname}_{author_safe}_{title_core}_s{sharpe.2f}.md
```

例: `2026_T07_板块轮动_Tcya_减法出奇迹_一个ETF轮动策略的科学提纯之路_s0.85.md`

- `year`: `published_at` 前 4 位
- `Tcode`: 12 大分类代码（T01~T12）
- `Tname`: 分类中文简称
- `author_safe`: 原作者名，**空白换 `-`**（跟主分隔符 `_` 不冲突，如 `will be rich man → will-be-rich-man`）+ 去文件系统非法字符，截 30 字符
- `title_core`: 标点换 `_`、去空白、合并连续下划线、截 50 字符
- `_s{sharpe.2f}`: 实测 Sharpe，2 位小数（如 `s0.85`），**放在文件名末尾**

**Agent 浓缩流程**：当文件名超过 80 字符时，agent 应在 `/tmp/jq_dedup_result.json` 的 `top3_after_dedup[i]` 里加 `condensed_title_core` 字段覆盖默认提取结果。脚本会优先用 agent 浓缩的版本。

## IMA 接口（智能降级 + WorkBuddy 强制连接器）

**WorkBuddy 内强制走连接器, 不允许降级到 HTTPS**。4 层连接器 + 1 个降级：

```
优先级 1: 环境变量 IMA_MCP_CALLBACK (Python 文件) → MCP 连接器  ← WorkBuddy 默认首选
优先级 2: 环境变量 IMA_CONNECTOR (脚本路径)        → connector 脚本
优先级 3: PATH 里的 `ima-connector` 命令           → connector 命令
优先级 4: 环境变量 WORKBUDDY_REQUIRE_CONNECTOR=1 时, 没 connector/MCP 就报错退出
优先级 5: (默认) 降级到直接 HTTPS (ima-openapi-clientid/apikey headers)
```

详见 `references/connectors.md`。

### 重要: WorkBuddy 内必须用连接器

设了 `WORKBUDDY_REQUIRE_CONNECTOR=1` 后, 脚本检测不到任何 connector/MCP 时会**直接报错退出**, 不会降级到 HTTPS。这是 WorkBuddy 的强制规则, 防止 HTTPS API 凭证问题导致流水线失败。

WorkBuddy 内调用方必须二选一:
- **MCP 优先**: 启用 `ima-mcp` MCP 服务 + 设置 `IMA_MCP_CALLBACK=<wrapper_path>`
- **Connector 备选**: 安装 `ima-connector` CLI, 或设置 `IMA_CONNECTOR=<脚本路径>`

## 分类逻辑

按 `references/classification.md` 中的 12 大分类决策树，**严格按代码特征**判定：

- T04 指数增强：`set_benchmark` AND `get_index_stocks` 都出现
- T02 均值回归：含 `reversal/反转/RSI/KDJ` 等反转特征
- T07 板块轮动：含 `get_industry_stocks/etf_pool` 等
- T09 技术形态：含 `CDL/形态/jqmt` 等
- T10 ML/AI：含 `XGBoost/LSTM/tensorflow`（**不是**单个 LinearRegression 导入）
- 其他分类依此类推

判定顺序：T04 (AND) → T08 → T02 → T10 → T03 → T06 → T05 → T07 → T09 → T11 → T12 → T01

## 避雷点

1. **积分耗尽**：回测会卡在 37%，需充值或等免费队列
2. **私库依赖**（`from jqmt import *`）：克隆不带私库，回测必失败
3. **IMA 无删除 / rename API**: 命名规则调整后, **存量条目按新规则走 IMA 重传** (旧条目留作历史)。IMA 上会同时存在新旧两种命名的同策略 markdown, 这是正常的。批量整理可参考 `IMA_策略重命名提示词.md` (在主项目目录)。
4. **回测时间 > 1h**：主人规则 (2026-07-28)，轮询超时 1 小时强制终止
5. **路径含空格**："vibe quant" 必须用双引号
6. **BT3 类策略**：缺私库的策略直接放弃，不要等
7. **Sharpe 太低**: Sharpe <= 0.8 视为低质策略，主人规则 (2026-07-28) 跳过
8. **Sharpe 过度拟合**: Sharpe > 3.0 视为过度拟合，主人规则 (2026-07-28) 跳过 (等于 3.0 通过)
9. **step4_poll.py check_sharpe 崩溃 (2026-07-29 修复)**: jqcli `backtest show` 在 running 状态时 `metrics` 字段是**空 list 不是 dict**，原版 `metrics.get("sharpe")` 直接抛 `AttributeError`。脚本已修：先看 `status=="running"` 短路返回 running；metrics 非 dict 也按 running 处理。如果轮询突然死在第一行 AttributeError，多半是这个坑回潮。
10. **step5_review_build.py author 字段兼容 (2026-07-29 修复)**: `/tmp/jq_dedup_result.json` 的 `top3_after_dedup` 候选中 `author` 在 `step1_filter.py` 原始输出里是 dict (`{id, name}`)，但 agent 在 step2 手动生成的简化版用的是 `author_name` 平铺字段。原脚本 `c["author"]["name"]` 在简化版上 KeyError。已修：build_review 兼容 dict 和 `author_name` 两种形态。WorkBuddy 内 agent 自己跑 step2 时务必走平铺简化版（节省 MCP 查重调用次数），脚本不能假设上游格式。
11. **step4_poll.py stdout 块缓冲 (2026-07-30 修复)**: Python pipe 模式默认 block buffering (4KB 才 flush), 跑后台 + `run_in_background=true` 时 `TaskOutput` 整小时看不到任何 print 输出，只能看 `/tmp/jq_real_sharpe.json` mtime 推断。已修：`sys.stdout.reconfigure(line_buffering=True)` + `sys.stderr.reconfigure(line_buffering=True)` (Python 3.7+), 老版本兜底 `PYTHONUNBUFFERED=1`。
12. **mcp__ima-mcp__add_knowledge 并发冲突 (2026-07-30 现身)**: WorkBuddy agent 跑 step 6 时如果**同时发起**多个 `add_knowledge` 调用，第二个会报 `222000 文件夹不存在`（实际存在）。IMA 服务端有 per-folder 锁。**WorkBuddy 内 agent 必须串行调用**: 一个 `add_knowledge` 全部完成后才发起下一个。建议在两次调用之间 sleep 0.5-1s 让服务端落库。脚本 `step6_upload.py` 用的是 for 循环（已串行），问题只在 agent 直接调 MCP 时出现。
13. **dedup_result.json content_preview 含双引号导致 JSON 解析失败 (2026-07-31 现身)**: agent 在 step2 手动生成 `/tmp/jq_dedup_result.json` 时复制了 step1 的 `content_preview` 字段，里面的中文 `"大A走弱"` 直接是 ASCII `"`，写入后 run_daily.sh 第 44-50 行 `json.load` 抛 `Expecting ',' delimiter: line 14 column 148`, try/except 静默返 0, 报"全部被查重"直接退出 step3 后续全空跑。**修法**: agent 写 dedup_result.json 时**不要带 content_preview 字段**, 或者预先 `replace('"', '\\"')` 转义。
14. **COS 上传 cos_key 复制粘贴陷阱 (2026-07-31 现身)**: `create_media` 返回的 cos_key 是 32字符hex + `.md`, 直接复制到 `python -c "..."` 的单行字符串里**容易丢字符** (32 → 31), 症状 `CosServiceError AccessDenied`, resource 字段显示跟传进去一致 (看着像没复制错), 实际长度差一。**修法**: 用 heredoc (`<< PYEOF`) 写脚本, key 单独一行; 上传前 `print('len:', len(key))` 长度校验 (应该 == 73 含 `2/cvh...md`)。或者把 create_media 返回的 JSON 整个 dump 到临时文件, 脚本 `json.load` 拿 cos_key, 不走人肉复制。
15. **step3_clone.py 默认 JQS 路径错 (2026-08-04 现身)**: `step3_clone.py:11` 默认 `JQS = /Users/ytf/Library/Python/3.9/bin/jqcli`, 但实际 jqcli 在 `/opt/miniconda3/bin/jqcli` 或 `/opt/miniconda3/envs/quantenv/bin/jqcli`, 直接跑 `bash run_daily.sh` 会报 `FileNotFoundError`。**修法**: 必须 `export JQS=/opt/miniconda3/bin/jqcli && bash run_daily.sh` **同一条命令** (子 shell 才会继承 export, 单独 export 无效)。建议改 step3 脚本默认值或加路径探测。
16. **cos-python-sdk-v5 ContentLength=int 报错 (2026-08-04 现身)**: `client.put_object(ContentLength=file_size)` (file_size 是 int) 抛 `InvalidHeader: Header part (N) must be of type str or bytes, not int`。**修法**: 不传 ContentLength 参数, SDK 会自动从 Body 计算。
17. **IMA KB 重建 (2026-08-05 解决, 2026-08-02 ~ 08-04 失效)**: `folder_7403603866166189` (聚宽量化策略库) 和 `folder_7460938768731745` (1.聚宽策略合集2026年) 在 YTF 的 KB (`0019ec5242003ac7`) 里报 `222000 文件夹不存在` 持续 4 天 (8/2 ~ 8/4)。8/5 主人新建独立 KB `7489478692198610` (聚宽量化策略库), 7 个年度子目录 (1.2026 / 2.2025 / 3.2024 / 4.2023 / 5.2022 / 6.2021 / 7.代码详注) 全在, 595+ 条历史策略完整迁移。**当前激活参数**:
    - KB ID: `7489478692198610` (聚宽量化策略库)
    - 目标 folder: `folder_7489478742522939` (1.聚宽策略合集2026年)
    - COS bucket: `ima-share-kb-1258344701` (新 KB 用 share bucket, 不是 `ima-media-prod`)
    - COS region: `ap-shanghai`
    - 历史 YTF 的 KB (`0019ec5242003ac7`) 和它的 folder 全失效, 不要用
    - 跨 KB 查重用 `mcp__ima-mcp__search_knowledge_base` 找新 KB ID, 不要凭印象
18. **Sharpe 0.7~0.8 观察名单 (2026-08-05 主人确认)**: 之前 `0.8 < sharpe <= 3.0` 直接跳过 < 0.8 的策略。8/5 主人确认可观察名单, 改规则为 `0.7 <= sharpe <= 3.0` 且 `<= 0.8` 的进 `/tmp/jq_watchlist.json` 保留观察 (不立刻入库), `> 0.8` 照常入库。**待实现**: step5_review_build.py 加 `--watchlist` flag + write `/tmp/jq_watchlist.json`; step6 跳过 watchlist 文件。
19. **jqcli 能力更新 (2026-08-16 同步)**: 本地 jqcli 已更新到含以下能力, 写新脚本时优先用原生命令而不是自写轮询/解析:
    - `backtest wait {bt_id} --wait-timeout 14400 --poll-interval 30`: 独立轮询**已有**回测, 不新建回测 (run --wait 每次调用都新建)。step4_poll.py 的自写轮询未来可迁移到这条命令 (注意它内部已处理 `metrics` 空 list 的坑, 见第 9 条)。
    - `backtest export {bt_id} --type all --output ./dir`: 导出日志/交易详情/持仓&收益/收益概述 4 件套; **导出的 CSV 是 GBK 编码**, 读取须 `encoding=gbk`。
    - `research ls/show/exec/run/kernels/sessions/...`: 新增研究平台文件管理 + 临时会话远端执行命令组; **需 Cookie 登录态** (只有 Bearer token 时先 `jqcli auth login`); 本流水线暂未用到, 但跨电脑移植验证时 `jqcli research ls` 可作为 Cookie 有效性检查。

## 关键约束 (主人规则 2026-07-28 / 2026-07-29)

- **每天独立完整任务**: 每日 automation 触发后, agent 跑完整 step 1-6, 不跨天接续
- **不用 launchd daemon**: 不安装后台服务, 完全靠 agent 任务窗口
- **step 4 用 run_in_background + TaskOutput**: agent 启动 step4_poll.py 后台跑, 用 TaskOutput 轮询输出, **超时 1 小时 (3600s) 强制终止**
- **Sharpe 过滤**: `0.8 < sharpe <= 3.0` (下限不带等号, 上限带等号)
- **入库命名**: `{year}_{Tcode}_{Tname}_{author}_{title_core}_s{sharpe}.md` (作者段空白换 `-`, Sharpe 段放最后, 总长 <= 80 字符, 无 Sharpe 省略段)
- **WorkBuddy 严格模式**: 必须用 MCP 连接器 (ima-mcp), 禁止降级 HTTPS API. 设 `WORKBUDDY_REQUIRE_CONNECTOR=1`

## WorkBuddy Agent 操作 SOP (step 6 MCP 上传)

**Step 6 串行上传** — agent 调 MCP 工具必须**串行**进行:

```python
for md in [/tmp/jq_uploads/*.md]:
    # 1) create_media (拿 media_id + cos_credential)
    # 拿到返回的 cos_credential 后, **不要再人肉复制 cos_key 到下一条 shell 命令**
    # 详见下方"防 cos_key 复制陷阱"小节
    media = await mcp.ima.create_media(...)
    # 2) 客户端用 cos-python-sdk-v5 PUT 文件 (用 cos_credential.bucket/region/keys/cos_key)
    upload_to_cos(md, media["cos_credential"])
    # 3) add_knowledge (串行!) — 一旦返回成功才能发起下一个
    await mcp.ima.add_knowledge(
        media_id=media["media_id"],
        folder_id=DEDUP.target_folder_id,
        kb_id=DEDUP.knowledge_base_id,
    )
    # 4) 短暂 sleep 让服务端落库, 避免下一轮并发锁
    await asyncio.sleep(0.5)
```

**为什么串行**: IMA 服务端 per-folder 有锁, 并发调 `add_knowledge` 时第二个会返回 `222000 文件夹不存在` (实际存在)。串行 + 0.5s sleep 稳过。

**为什么不能用脚本**: `step6_upload.py` 用 `ima_api` (HTTPS/connector 模式), 不被 `WORKBUDDY_REQUIRE_CONNECTOR=1` 接受。WorkBuddy 内 agent 必须直接调 MCP。

### 防 cos_key 复制陷阱 (2026-07-31 修复)

`create_media` 返回的 `cos_key` 是 32字符hex + `.md`, 直接复制到 `python -c "..."` 单行字符串里容易丢字符。**正确做法**:

**方案 A: heredoc 写脚本 + 单独 key 行 + 长度校验 (推荐)**
```python
# 把 create_media 整个返回 JSON dump 到临时文件
import json
cred = json.loads(open('/tmp/cos_cred_1.json').read())
key = cred['cos_credential']['cos_key']
assert len(key) == 73, f"cos_key 长度异常: {len(key)} != 73"  # 2/cvh...{32hex}.md
# ... 用 key 调 cos SDK
```

**方案 B: 把 cred 直接传给 python 脚本, 不要再 shell 里手抄**
```bash
# create_media 后把 cred dump 到文件
echo "$RESPONSE" > /tmp/cos_cred_1.json
# 然后用脚本读, 不走人肉复制
python3 upload_one.py /tmp/jq_uploads/foo.md /tmp/cos_cred_1.json
```

**绝对禁止**: 把 `cos_key` 直接复制粘贴到 `python3 -c "..."` 的单行字符串里 — 32位hex 太容易漏一字符, 错误信息还显示 resource 路径正常, 极难调试。

## 安装步骤

```bash
# 1. 拉取 skill
git clone https://github.com/Joseph2Young/jq-daily-pipeline.git
# 或:  npx degit Joseph2Young/jq-daily-pipeline ~/path/to/install

# 2. 放脚本到工作目录
mkdir -p "/Users/{user}/Desktop/vibe quant/jq_daily_pipeline"
cp jq-daily-pipeline/scripts/* "/Users/{user}/Desktop/vibe quant/jq_daily_pipeline/"

# 3. 配 IMA 凭证
mkdir -p ~/.config/ima
echo "your_client_id" > ~/.config/ima/client_id
echo "your_api_key" > ~/.config/ima/api_key
chmod 600 ~/.config/ima/*

# 4. 替换路径
sed -i '' "s|/Users/ytf|$HOME|g" "/Users/{user}/Desktop/vibe quant/jq_daily_pipeline/scripts/"*

# 5. 跑一次
bash "/Users/{user}/Desktop/vibe quant/jq_daily_pipeline/run_daily.sh"
```

## 定时调度（按 Agent 选）

| Agent | 调度方式 | 详见 |
|---|---|---|
| **Codex** | 「已安排任务」面板 | `agent_scheduled_task.md` |
| **Claude Code** | Cron + skill prompt | `agent_scheduled_task.md` |
| **Cursor** | IDE 调度 / 手动 | `agent_scheduled_task.md` |
| **GitHub Actions** | `.github/workflows/` | `agent_scheduled_task.md` |
| **macOS launchd** | `~/Library/LaunchAgents/` | `agent_scheduled_task.md` |
| **Linux cron** | `crontab -e` | `agent_scheduled_task.md` |

## 验证清单

```bash
# 工具
which jqcli && jqcli --help
jqcli auth status
python3 -c "import requests; print(requests.__version__)"

# 凭证
cat ~/.config/ima/client_id | head -c 20
cat ~/.config/ima/api_key | head -c 20

# IMA 客户端自测
python3 scripts/ima_api.py
# 应显示: 模式: direct 或 connector:xxx 或 mcp:xxx

# 单步测试
python3 scripts/step1_filter.py
python3 scripts/step2_ima_dedup.py
```

## 用户故事

**用户**: "今天有什么新的聚宽策略？"
**AI**: 触发 skill → 拉 Top 3 → 跑回测 → 审查改名 → 库到 IMA

**用户**: "把这个工作流复制到我的新电脑"
**AI**: git clone 整个 skill → 改路径 → 配凭证 → 配置定时任务

**用户**: "调整阈值到 1.5" / "改成晚上 10 点跑" / "改命名规则"
**AI**: 改 `references/parameters.md` 或具体脚本的常量

**用户**: "我装了一个 IMA connector，怎么用？"
**AI**: 看 `references/connectors.md` → 设置 `IMA_CONNECTOR` 环境变量
