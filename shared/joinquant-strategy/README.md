# joinquant-strategy

聚宽(JoinQuant)本地文档检索 skill。

## 这是什么

把 joinquant.com 的官方 **API 文档 + 数据字典**镜像到本地，结构化成可被大模型按章节检索的知识底座。

- `api/`：API 文档（77 个 markdown chunk）
- `data/`：数据字典（15 个主题，1694 个 markdown chunk）

## 快速开始

1. 读 [`SKILL.md`](./SKILL.md) 了解使用规则。
2. 写回测策略时，从 `api/index.md` 入口检索。
3. 写 Notebook 分析代码时，从 `data/index.md` 入口检索。
4. 按 9 条检索规则按需读 chunk，**不要**把整个目录塞进上下文。

## 数据来源

- 同步源：`https://www.joinquant.com/help/api/help` 和 `https://www.joinquant.com/data`
- 镜像快照：见 [`SOURCE_README.md`](./SOURCE_README.md)（原 `Downloads/joinquant/README.md`）
- 本 skill 是**文档缓存层**，不是平台数据替代品。回测和实盘仍以 joinquant.com 实际执行为准。

## 安全

本 skill 全部内容来自 joinquant.com 公开文档。完整审查报告见 [`SECURITY_AUDIT.md`](./SECURITY_AUDIT.md)。

## 版本

- version: 1.0.0
- slug: `joinquant-strategy`
