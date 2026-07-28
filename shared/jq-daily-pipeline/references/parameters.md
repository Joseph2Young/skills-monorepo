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
| **Sharpe 阈值** | **≥ 1.0** | 低于则不入选库 |
| 名称相似度阈值 | 80% | 超过视为雷同，只保留一个 |
| 代码相似度阈值 | 80% | 同上，基于 difflib.SequenceMatcher |

## 命名格式

**`{年份}_{类型编号}_{类型简称}_{原标题核心}.md`**

示例：
- `2026_T02_均值回归_高胜率70%ETF策略.md`
- `2026_T07_板块轮动_量化人破防了_五福同一套框架优化后_8年收益差出345万.md`

## 分类阈值词（按决策树）

| 类型 | 关键阈值词（任一匹配） |
|---|---|
| T01 趋势跟踪 | momentum, MA, EMA, 均线, 金叉, 多头排列, ADX, 唐奇安, 动量 |
| T02 均值回归 | RSI, KDJ, 布林, BIAS, 乖离, reversal, 反转, 超卖 |
| T03 多因子选股 | get_fundamentals, get_factor_values, Alpha101, Alpha191 |
| T04 指数增强 | **set_benchmark AND get_index_stocks** (都需出现) |
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
| 聚宽量化策略库 folder_id | 在知识库下查 "聚宽量化策略库" |
| 1.聚宽策略合集{YYYY}年 folder_id | 在聚宽量化策略库下查 "1.聚宽策略合集{YYYY}年" |
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
3. **IMA 无删除 API**：命名规则确定后别改
4. **回测 > 24h**：7.5 年可能 5+ 小时
5. **路径含空格**："vibe quant" 必须双引号
