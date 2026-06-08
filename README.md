# Skills Monorepo

统一管理 Codex + Claude Code 的 skills 仓库，消除重复，macOS + Parallels Windows 双端共享。

## 目录结构

```
~/skills-monorepo/
├── shared/          # Codex + Claude Code 共用的 skills（54个）
├── project/         # 项目级 skills（如 sop-factory）
├── codex-system/    # Codex 内置 skills 的备份（仅供参考，不由本仓库管理）
├── install.sh       # macOS 一键安装
├── install.ps1      # Parallels Windows 一键安装
├── uninstall.sh     # macOS 卸载
└── README.md
```

## 工作原理

所有 skill 文件只存在于 ~/skills-monorepo/ 中。各工具通过 symlink 读取：

| 工具路径 | 类型 | 指向 |
|---------|------|------|
| ~/.agents/skills/ | 目录级 symlink | -> monorepo/shared/ |
| ~/.codex/skills/{skill}/ | 逐个 symlink | -> monorepo/shared/{skill}/ |
| ~/.claude/skills/{skill}/ | 逐个 symlink | -> monorepo/shared/{skill}/ |
| 项目 .agents/skills/{skill}/ | 逐个 symlink | -> monorepo/project/{skill}/ |
| 项目 skills/{skill}/ | 逐个 symlink | -> monorepo/project/{skill}/ |

~/.codex/skills/.system/ 是 Codex 内置目录，不纳入管理。

## macOS 安装

```bash
bash ~/skills-monorepo/install.sh
```

## Parallels Windows 安装

前提：Parallels 共享文件夹已启用（Mac Home 映射到 \\Mac\Home）。

```powershell
powershell -ExecutionPolicy Bypass -File \\Mac\Home\skills-monorepo\install.ps1
```

## 添加新 skill

1. 将 skill 目录放入 shared/（全局）或 project/（项目级）
2. 重新运行 install.sh 或 install.ps1
3. 提交 Git

```bash
cd ~/skills-monorepo
git add shared/新skill名/
git commit -m "添加新 skill: 新skill名"
```

## 卸载/回滚

```bash
bash ~/skills-monorepo/uninstall.sh
```

卸载只删除 symlink，不删除 monorepo 中的实际文件。如需恢复，重新运行 install.sh 即可。

## 同步到其他 Mac

```bash
git clone <repo-url> ~/skills-monorepo
bash ~/skills-monorepo/install.sh
```
