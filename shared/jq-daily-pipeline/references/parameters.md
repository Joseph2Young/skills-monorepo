# 关键参数表

## 时间相关

| 参数 | 默认值 | 说明 |
|---|---|---|
| 触发时间 | 09:00 | 每天上午 9 点（在 Codex agent 内配置） |
| 时间窗口 | 过去 24 小时 | 拉 `now - 24h` 到 `now` 之间发布的策略 |
| 回测窗口 | 2019-01-01 ~ T-1 | 7.5 年（聚宽历史数据起点） |
| 拉取页数 | 30 页 | 每页 50 条，共 1500 条候选 |

## 过滤阈值

| 参数 | 默认值 | 说明 |
|---|---|---|
| **Sharpe 阈值** | **0.8 < s <= 3.0** (下限不带等号, 上限带等号) | 低于 0.8 (含 0.8) 跳过, 高于 3.0 (不含 3.0) 视为过度拟合 |
| 名称相似度阈值 | 80% | 超过视为雷同，只保留一个 |
| 代码相似度阈值 | 80% | 同上，基于 difflib.SequenceMatcher |

## 命名格式

**`{年份}_{T编号}_{T简称}_{作者}_{标题核心}_s{Sharpe.2f}.md`**

字段处理:
- `year`: `published_at` 前 4 位
- `Tcode`: 12 大分类代码 (T01~T12)
- `Tname`: 分类中文简称
- `author`: 作者名, **空白换 `-`** (跟主分隔符 `_` 不冲突) + 去文件系统非法字符, 截 30 字符
- `title_core`: 标点换 `_`、去空白、合并连续下划线、截 50 字符
- `_s{sharpe.2f}`: 实测 Sharpe, 2 位小数, **放在文件名末尾**
- **总长度上限 80 字符** (含 `.md` 后缀), 超阈值由 agent 主动浓缩 title_core
- **没有回测的策略**: 文件名省略 `_s{sharpe}` 段 (不写 _s0 / _s? / _sNA)

示例:
- `2026_T02_均值回归_星星的碎片_高胜率70%ETF策略_s1.45.md`
- `2026_T07_板块轮动_Tcya_减法出奇迹_一个ETF轮动策略的科学提纯之路_s0.85.md`
- (无 Sharpe) `2026_T09_技术形态_阿萨德szx_不择时小市值弱转强.md`

## 分类阈值词（按决策树）

| 类型 | 关键阈值词（任一匹配） |
|---|---|
| T01 趋势跟踪 | momentum, MA, EMA, 均线, 金叉, 多头排列, ADX, 唐奇安, 动量 |
| T02 均值回归 | RSI, KDJ, 布林, BIAS, 乖离, reversal, 反转, 超卖 |
| T03 多因子选股 | get_fundamentals, get_factor_values, Alpha101, Alpha191 |
| T04 指数增强 | **set_benchmark AND get_index_stocks AND 中文"指数增强"** (三个 AND 命中, 2026-08-01 加严避免误判, 决策树末尾) |
| T05 事件驱动 | 业绩预告, 回购, 分红, 事件, 公告 |
| T06 资金流向 | 北向, 融资余额, 龙虎榜, 大单, 资金流 |
| T07 板块轮动 | get_industry_stocks, get_concept_stocks, ETF池, etf_pool |
| T08 统计套利 | 协整, 价差, Z-score, 对冲, pairs |
| T09 技术形态 | CDL, W底, 旗形, 吞没, 锤子, jqmt |
| T10 ML/AI 选股 | XGBoost, LSTM, tensorflow, torch, RandomForest (单个 LinearRegression 不算) |
| T11 波动率策略 | ATR, vol-targeting, 波动率 |
| T12 成长股策略 | PEG, 高增速, inc_revenue |

## IMA 关键 ID（每台电脑不同，需重新查询）

| 资源 | 查找方法 |
|---|---|
| YTF的知识库 | `openapi/wiki/v1/search_knowledge_base` 查 "YTF" |
| 聚宽量化策略库 folder_id | 在知识库下查 "聚宽量化策略库" (**2026-08-02 起作为入库目标文件夹, 不再按年度分子文件夹**) |
| ~~1.聚宽策略合集{YYYY}年 folder_id~~ | (2026-08-02 起废弃) 历史策略仍留在该子文件夹, 新策略直接进聚宽量化策略库 |
| 凭证 | `~/.config/ima/client_id` 和 `~/.config/ima/api_key` |

## IMA API 端点

Base URL: `https://ima.qq.com`

| API | 用途 |
|---|---|
| `POST /openapi/wiki/v1/search_knowledge_base` | 查知识库 |
| `POST /openapi/wiki/v1/get_knowledge_list` | 列文件夹内容 |
| `POST /openapi/wiki/v1/create_folder` | 新建文件夹 |
| `POST /openapi/wiki/v1/check_repeated_names` | 查重 |
| `POST /openapi/wiki/v1/create_media` | 创建媒体 + 拿 COS 凭证 |
| `POST /openapi/wiki/v1/add_knowledge` | 关联到知识库 |

认证 Header:
- `X-IMA-CLIENTID: <client_id>`
- `X-IMA-APIKEY: <api_key>`

## 避雷点

1. **积分耗尽**：回测卡在 37%，需充值
2. **私库依赖**：`from jqmt import *` → 克隆不带私库，回测必失败
3. **IMA 无删除 / rename API**: 命名规则调整后, 存量策略按新规则走 IMA 重传, 旧条目留作历史。IMA 上会同时存在新旧两种命名的同策略 markdown, 这是正常的。
4. **回测 > 24h**：7.5 年可能 5+ 小时
5. **路径含空格**："vibe quant" 必须双引号
6. **step4_poll.py stdout 块缓冲 (2026-07-30 修复)**: pipe 模式下默认块缓冲, run_in_background + TaskOutput 看不到 print。已加 `sys.stdout.reconfigure(line_buffering=True)`。
7. **mcp__ima-mcp__add_knowledge 并发冲突 (2026-07-30 现身)**: IMA 服务端 per-folder 锁, agent 并发两个 add_knowledge 第二个报 222000。WorkBuddy 内必须**串行调用 + sleep 0.5~1s**。
8. **T04 误判 (2026-08-01 加严)**: 原 `set_benchmark AND get_index_stocks` 太宽松, 几乎所有策略命中。已修: T04 移到决策树末尾 + AND 增加中文"指数增强"关键词。回归测试: 科技股ETF → T07, 小市值龙头 → T03。
9. **入库文件夹路径调整 (2026-08-02 主人规则)**: 不再按年度分子文件夹, 新的入库目标直接是 `聚宽量化策略库` (`folder_7403603866166189`)。历史的 `1.聚宽策略合集{YYYY}年` 子文件夹保留不动, 不迁移。**dedup_result.json 写 `target_folder_id = folder_7403603866166189`**。
