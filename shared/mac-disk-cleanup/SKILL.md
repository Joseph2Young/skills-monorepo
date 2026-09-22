---
name: mac-disk-cleanup
description: macOS 磁盘空间体检与安全清理。当主人提出「磁盘满了」「空间不够」「帮我看看什么值得清理」「系统盘红了」「清理缓存」「找出重复文件」等诉求时使用。流程为：只读扫描出分级报告 → 确认后分批移入废纸篓 → 输出执行报告与恢复映射。全程可恢复，不碰工作数据。
agent_created: true
---

# macOS 磁盘清理体检

## 核心原则（不可违背）

1. **第一轮永远只读。** 无论主人怎么说「直接清掉」，第一次接触必须先扫描并出分级报告，让主人看到清单再动手。
2. **删除一律走废纸篓。** 用 `mv` 移到 `~/.Trash`，禁止 `rm -rf`。个人目录（Desktop / Downloads / Documents / Home）尤其禁止。
3. **每批不超过 10 项**，每批后验证。
4. **工作数据不碰**：行内应用数据（如 `~/.scbank`）、正式公文、量化策略源码与数据、各项目的独立资源文件。
5. **生成恢复映射表**，记录每项「原始路径 → 废纸篓位置」。

## 三个必须预先知道的环境坑

### 坑 1：废纸篓读写受限，无法代为清空

`~/.Trash` 在沙盒下会报 `Operation not permitted`；用 `osascript` 控制 Finder 清空会报权限违例 `-10004`。

- **后果**：移入废纸篓后磁盘空间**不会释放**，必须由主人在 Finder 中按 `⌘ Command + ⇧ Shift + ⌫ Delete` 手动清空。
- **注意**：沙盒有时允许读 `~/.Trash`、有时不允许。**不要**用 `ls ~/.Trash | wc -l` 得到 0 就判断废纸篓为空——那是权限被拒。
- **判断文件是否真的移走**：直接检查原路径是否存在（`[ -e "$src" ]`），不要依赖废纸篓列表。

### 坑 2：大批量 mv 触发 broker IPC 超时

`mv` 大量文件时可能报：

```
Broker request timed out
（来自 WorkBuddy.app/Contents/Resources/app.asar.unpacked/cli/vendor/shim/broker-ipc-client.cjs）
```

- 单次移动 **1.5 万个文件级别的目录必失败**（实测 node_modules 15690 文件）。
- 对策：**拆成子目录粒度逐个移动，并带重试**。实测拆成 105 项后全部成功。
- **文件名含中文书名号《》等特殊字符也会触发超时**，重试 2–3 次通常能过。
- 重试模板：

```bash
for attempt in 1 2 3; do
  mv "$p" "$dst" 2>/dev/null && break
  sleep 1
done
```

### 坑 3：命令可能被重放，出现「文件莫名消失」

实测遇到过同一条命令被执行两遍：第一遍部分成功、第二遍其余成功，导致映射表出现重复记录、某几项显式报 `SKIP不存在`。

- **不要慌，也不要下结论说文件丢了。** 先看映射表和磁盘已用空间：空间没释放说明文件都在废纸篓里，没有不可逆丢失。
- 检查原路径状态 + `df -h` 对比即可判断。

## 执行流程

### 第 1 步：磁盘现状

```bash
df -h /System/Volumes/Data | tail -1
```

占用率超过 85% 即建议清理，超过 90% 属告急。

### 第 2 步：扫描体积地图

```bash
cd ~ && du -sh .[!.]* * 2>/dev/null | sort -rh | head -70
du -sh ~/Library/* 2>/dev/null | sort -rh | head -20
du -sh "$HOME/Library/Application Support"/* 2>/dev/null | sort -rh | head -15
du -sh ~/Library/Caches/* 2>/dev/null | sort -rh | head -25
```

对体积异常的目录逐层下钻：

```bash
for d in .cache .npm .local .codex .workbuddy; do
  echo "== $d =="; du -sh ~/$d/* 2>/dev/null | sort -rh | head -8
done
```

### 第 3 步：重复文件检测

用 `scripts/find_duplicates.py`（按文件大小分组 → 同尺寸组内算 MD5，阈值可调）：

```bash
python3 scripts/find_duplicates.py ~/Downloads ~/Desktop ~/Documents ~/WorkBuddy
```

**关键判断**：重复 ≠ 多余。以下情形不要删：

- 各项目 `images/` 下的封面图——看着是同名同内容，实为**每个项目的独立资源**
- 行内正式公文的两个副本——可能是**有意的版本对照**
- 程序依赖库的多个副本（如 `mini_racer.dll` 在 `trader_tool/` 与 `utils/`）——程序按不同相对路径加载
- 分发给不同批次学员的模板文件

只有**渲染管线中间产物**（`sources/*_files/`、`validation/readback_files/`）是真正安全的清理对象。

### 第 4 步：分级报告

分三档，每项都要有**体积 + 完整路径 + 判断依据**：

| 档位 | 含义 |
|---|---|
| **A 级** | 纯缓存/日志/临时解包，删了自动重建，无任何配置或数据损失 |
| **B 级** | 有取舍，需主人判断（重复副本、安装包、旧版本留存、用途不明目录） |
| **C 级** | 建议保留（工作数据、运行时、配置、官方材料） |

报告用 `show_widget` 或输出 HTML 文件，包含体积条形可视化。

### 第 5 步：确认后分批执行

用 `scripts/trash_move.sh`（会写恢复映射表）：

```bash
source trash_move.sh
move "$HOME/.npm/_cacache"
```

批次建议：

1. 开发工具缓存（npm / uv / codex-runtimes / chromium）
2. 应用缓存（各 App 的 Cache / ShipIt / BundleMigration）
3. 日志与临时产物
4. 大块重复环境（占收益最大头）
5. 项目冗余（node_modules / .git）
6. 重复文件管线副本

### 第 6 步：执行报告

必须包含：

- 已清理总量、逐批明细、路径
- **主动跳过的项 + 理由**（这部分比清理清单更能体现判断力）
- 恢复方式（废纸篓「放回原处」+ 映射表路径）
- **待主人操作：清空废纸篓**（给出 `⌘⇧⌫` 指引）
- 如实说明执行异常（超时、重放等）

## 常见可清项速查

| 路径 | 典型体积 | 说明 |
|---|---|---|
| `~/.npm/_cacache`、`_npx` | 1–2 GB | npm 缓存 |
| `~/.cache/codex-runtimes` | 1.5 GB | 运行时缓存 |
| `~/.cache/uv`、`~/.local/share/uv` | 0.5 GB | uv 缓存 |
| `~/.chromium-browser-snapshots` | 0.3 GB | 浏览器快照 |
| `~/Library/Caches/*.ShipIt` | 0.5–1 GB | VSCode 等更新残留 |
| `~/Library/Caches/*.BundleMigration` | ~1 GB | 应用升级临时解包 |
| `~/.workbuddy/logs`、`traces` | 0.5 GB | 日志与追踪 |
| `~/.claude-science/conda/pkgs` | ~1 GB | conda 包缓存 |
| 各 App `Application Support` 的 Cache | 0.3–1 GB/个 | 网页与代码缓存 |

## 绝对不动的项

- `~/.workbuddy/binaries` —— **运行时地基，不是缓存**。含 python/envs（default、scrc、docx-reader、ima_cos）、node/versions。删了 WorkBuddy 的 Python/Node 能力与相关技能一起废掉。
- 行内应用数据（`~/.scbank` 等）
- `~/skills-monorepo`（含 git 历史）
- 各 AI 工具的配置与凭证（`~/.csswitch/config.json` 等）
- 应用的登录态目录（豆包 `Default`/`sdk_storage`、WorkBuddy `WebStorage`）——建议走应用内清理

## 未覆盖范围（可主动提示主人单独排查）

iCloud 云盘、Parallels 虚拟机镜像、Docker 镜像、macOS 系统区、其他用户账户。虚拟机镜像动辄几十 GB，是最容易被忽略的吨位级占用。
