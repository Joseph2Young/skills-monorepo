# JoinQuant 本地资料镜像

这里保存的是 JoinQuant 的 API 文档和数据字典的本地镜像。目标不是做给人逐页阅读的手册，而是做给大模型或编程助手按需检索的知识底座。

这样做的目的很直接：

- 不需要每次都重新访问网页
- 不需要把整个站点塞进上下文
- 可以先本地检索，再决定要不要继续读更细的章节

这不是 `skill` 包装，而是一个更通用的资料层。任何能读本地文件的编程助手都可以直接用，包括 Codex、Claude Code、Cursor、Copilot Chat 这类工具。

## 目录结构

### `api/`

JoinQuant API 文档镜像，对应 `https://www.joinquant.com/help/api/help#name:api`

- `index.md`：入口索引，先看它再决定读哪些章节
- `manifest.json`：机器可读清单，包含来源、chunk 数量和 chunk 元数据
- `tree.json`：原始章节树，适合按标题定位
- `raw/api.html`：原始 HTML 备份，只有在需要回看原始结构时才打开
- `chunks/*.md`：按章节切分后的内容

### `data/`

JoinQuant 数据字典镜像，对应 `https://www.joinquant.com/data`

- `index.md`：数据字典入口索引
- `manifest.json`：数据主题清单
- `raw/data.html`：数据页入口 HTML
- `<DocName>/`：每个数据主题一个子目录，例如 `Stock`、`index`、`Future`、`Option`、`fund`、`Alpha101`、`Alpha191`、`JQDatadoc` 等
- 每个子目录里同样有 `index.md`、`manifest.json`、`tree.json`、`raw/*.html`、`chunks/*.md`

## 给大模型的检索规则

1. 先判断任务属于 `api` 还是 `data`。
2. 先读对应目录的 `index.md`。
3. 默认直接读与问题相关的 `chunks/*.md`。
4. 只有在需要总览、批量筛选、确认 `chunk_count` 或定位文件路径时，再读 `manifest.json`。
5. 需要章节层级时读 `tree.json`。
6. 如果某个章节被拆成 `0039.01.md` 这种形式，就按数字顺序把整组读完。
7. 只在 markdown 不能满足时再回到 `raw/*.html`。
8. 优先用文件名、`name` 和标题做检索锚点，不要依赖展示文本是否完整渲染。
9. 每个 chunk 开头的 `> Path:` 是路径面包屑，适合快速确认上下文位置。

## 使用方式

### 方式一：写回测策略

- 在本地用这里的文档查 API。
- 让助手生成策略代码。
- 把代码复制到 JoinQuant 的回测编辑器里运行。
- 这里的镜像只负责帮你更快写代码，不替代平台回测环境。

### 方式二：写分析代码

- 在本地用这里的文档查数据字典和 API。
- 让助手生成分析代码。
- 把代码复制到 JoinQuant 提供的 Notebook / research 环境里执行。
- 这条路径适合数据分析、特征验证、结果检查。
- 目前不把本地 SDK 作为主路径，避免为了拿到平台数据而额外引入付费依赖。

## 推荐工作流

1. 把整个 `docs/joinquant/` 目录复制到你的项目里。
2. 先让编程助手读这份 `README.md`。
3. 再让它读对应的 `api/index.md` 或 `data/index.md`。
4. 让助手只继续打开相关 chunk，而不是把整个目录一次性塞进上下文。
5. `manifest.json` 只在需要做目录总览、批量检索或路径核对时再读。
6. 完成后，把代码回贴到 JoinQuant 网站执行。

## 更新镜像

如果 JoinQuant 文档更新了，就重新跑同步脚本：

```powershell
D:\venvs\base-314\Scripts\python.exe sync_joinquant_api.py
D:\venvs\base-314\Scripts\python.exe sync_joinquant_data.py
```

同步后建议检查：

- `docs/joinquant/api/manifest.json`
- `docs/joinquant/data/manifest.json`
- 各自的 `index.md`

## 说明

- 这些文件是 UTF-8。
- 如果 PowerShell 里中文看起来乱码，通常是控制台编码问题，不代表文件坏了。
- 这份镜像是文档缓存层，不是平台数据的替代品。最终回测和分析仍以 JoinQuant 网站实际执行结果为准。
- 如果以后想把这套资料包装成某个助手的专用 `skill`，可以直接复用这里的检索规则，但默认保持为通用资料包更稳。

## 一个可直接给助手的提示词

> 先阅读 `docs/joinquant/README.md`，再按 `api/index.md` 或 `data/index.md` 读取相关章节。目标是生成可直接粘贴到 JoinQuant 回测编辑器或 Notebook 的代码，只保留与当前任务有关的最小上下文，不要重新抓取网站。
