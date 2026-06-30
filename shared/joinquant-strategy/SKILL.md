# joinquant-strategy Skill

聚宽(JoinQuant)本地文档检索器，为大模型提供按需检索的 JQ 知识底座。

## 定位

这不是策略模板生成器，而是 JQ 平台**官方 API 文档 + 数据字典**的本地镜像检索器。所有内容均同步自 joinquant.com 公开文档。

## 目录结构

```
joinquant-strategy/
├── SKILL.md                # 本文件
├── README.md               # 面向用户的简介
├── _meta.json              # slug / version
├── SECURITY_AUDIT.md       # 安全审查报告
├── SOURCE_README.md        # 原始资料包说明（来自 Downloads/joinquant/README.md）
├── api/                    # JQ API 文档镜像（77 个 chunk）
└── data/                   # JQ 数据字典镜像（1694 个 chunk，15 个主题）
```

### `api/` 镜像自 `https://www.joinquant.com/help/api/help`

- `index.md`：入口索引，列出 77 个章节
- `manifest.json`：机器可读清单
- `tree.json`：原始章节树
- `raw/api.html`：原始 HTML 备份
- `chunks/0001.md … 0077.md`：按章节切分的内容

### `data/` 镜像自 `https://www.joinquant.com/data`

- `index.md`：数据字典总入口（15 个主题）
- `manifest.json`：主题清单
- `raw/data.html`：原始 HTML
- `<DocName>/`：每个数据主题一个子目录（Stock / Future / Option / fund / Alpha101 / Alpha191 / factor_values / JQDatadoc / bond / macroData / plateData / index / OTCfund / Public / technicalanalysis），每子目录同样有 `index.md` / `manifest.json` / `tree.json` / `raw/` / `chunks/`

## 检索规则（务必遵守）

1. 先判断任务属于 `api` 还是 `data`。
2. 先读对应目录的 `index.md`。
3. 默认直接读与问题相关的 `chunks/*.md`。
4. 只有在需要总览、批量筛选、确认 `chunk_count` 或定位文件路径时，再读 `manifest.json`。
5. 需要章节层级时读 `tree.json`。
6. 如果某个章节被拆成 `0039.01.md` 这种形式，就按数字顺序把整组读完。
7. 只在 markdown 不能满足时再回到 `raw/*.html`。
8. 优先用文件名、`name` 和标题做检索锚点，不要依赖展示文本是否完整渲染。
9. 每个 chunk 开头的 `> Path:` 是路径面包屑，适合快速确认上下文位置。

## 使用流程

### 写回测策略

1. 读 `api/index.md` 找到相关章节（例如 `0039 数据获取函数`）。
2. 读对应 `chunks/0039.0X.md` 了解具体函数签名。
3. 读 `data/<DocName>/index.md` 确认数据结构。
4. 生成代码时**只引用读过的 chunk**，不要凭印象造函数。

### 写 Notebook 分析代码

1. 读 `data/index.md` 锁定数据主题。
2. 读 `data/<DocName>/chunks/` 里相关 chunk。
3. 优先用 JQData 路径（`data/JQDatadoc/`），避免在本地另装付费 SDK。

## 注意事项

- 本 skill 是**文档缓存层**，不是平台数据替代品。回测和实盘仍以 joinquant.com 实际执行为准。
- 所有内容是 UTF-8 文本，PowerShell 中文乱码是控制台编码问题，不是文件问题。
- 不要把整个目录一次性塞进上下文；按上面 9 条规则按需读取。
- 早期版本（v0.1.0）下被废弃的 `templates/` `snippets/` `api_reference/` `examples/` 现位于 `.deprecated/`，不再引用，可直接删除。

## 版本信息

- slug: `joinquant-strategy`
- version: 1.0.0
- 数据源：joinquant.com（最后一次同步见 SOURCE_README.md）
