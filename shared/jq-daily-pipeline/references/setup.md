# 跨电脑移植清单

## 目标

在另一台电脑上重新搭建这个 skill（同样的工具，不同的 IMA 账号/路径）。

## 步骤

### 1. 安装基础工具

```bash
# jqcli
pip3 install jqcli
jqcli auth status  # 登录聚宽

# Python 依赖
pip3 install requests

# 验证
which jqcli && jqcli --help
python3 -c "import requests; print('OK')"
```

### 2. 准备 IMA 凭证

1. 去 https://ima.qq.com/agent-interface 申请 Client ID + API Key
2. 保存到本地：
   ```bash
   mkdir -p ~/.config/ima
   echo "your_client_id" > ~/.config/ima/client_id
   echo "your_api_key" > ~/.config/ima/api_key
   chmod 600 ~/.config/ima/*
   ```

### 3. 放置脚本

```bash
# 创建工作目录（按你电脑的用户名）
mkdir -p "/Users/{user}/Desktop/vibe quant/jq_daily_pipeline"

# 复制 scripts/
cp -r {skill_path}/scripts/* "/Users/{user}/Desktop/vibe quant/jq_daily_pipeline/"
chmod +x "/Users/{user}/Desktop/vibe quant/jq_daily_pipeline/run_daily.sh"
```

### 4. 替换路径占位符

把所有 `scripts/*.py` 和 `scripts/*.sh` 中的：
- `/Users/{user}` 改为实际 macOS 用户名（如 `/Users/jane`）
- `/tmp/jq_*` 路径可保留（macOS /tmp 是统一的）

可以用 sed 批量替换：
```bash
WORK="/Users/yourname/Desktop/vibe quant/jq_daily_pipeline"
sed -i '' "s|/Users/{user}|$WORK|g" "$WORK"/scripts/*
```

### 5. 重新查询 IMA 关键 ID

**每台电脑的 IMA 知识库 ID 都不同**，必须重新查：

```bash
export IMA_CID="your_client_id"
export IMA_KEY="your_api_key"

# 1. 查 YTF 知识库 ID
curl -s -X POST "https://ima.qq.com/openapi/wiki/v1/search_knowledge_base" \
  -H "X-IMA-CLIENTID: $IMA_CID" -H "X-IMA-APIKEY: $IMA_KEY" \
  -d '{"query":"YTF","cursor":"","limit":5}'

# 2. 拿到 kb_id 后查聚宽量化策略库 folder_id (2026-08-02 起, 这是入库目标文件夹)
# 注: 不再查 "1.聚宽策略合集2026年" 子文件夹, 新的入库直接进"聚宽量化策略库"根
```

把这些 ID 替换到 `scripts/ima_api.py` 的 `KB_ID` 和 `TARGET_FOLDER_ID` 默认值, 或通过环境变量 `IMA_KB_ID` / `IMA_TARGET_FOLDER_ID` 注入。

### 6. 在 Codex agent 里设置定时任务

1. 打开 Codex 桌面端 → 「已安排任务」面板
2. 新建任务，触发时间 **每天 09:00**
3. 提示词见 `agent_scheduled_task.md`
4. 启用任务

### 7. 验证

```bash
# 跑一次完整流水线
bash "/Users/yourname/Desktop/vibe quant/jq_daily_pipeline/run_daily.sh"

# 看日志
tail -50 /tmp/jq_$(date +%Y%m%d).log

# 立即试跑（不等 9 点）
# 在 Codex agent 里直接说："现在跑一下 jq-daily-pipeline"
```

## 常见问题

**Q: IMA 凭证错误**
A: 检查 ~/.config/ima/client_id 和 api_key 是否有换行/空格

**Q: 知识库 ID 不对**
A: 用 search_knowledge_base 重新查，注意区分个人知识库和订阅知识库

**Q: jqcli 报"积分余额已不足"**
A: 充值聚宽积分或加 `--use-credit` 标志

**Q: BT3 类策略跑不动**
A: 缺私库（如 jqmt），跳过即可，代码会自动放弃

**Q: 命名规则要不要改**
A: 改前评估成本:
- IMA 无删除 / rename API, 改后旧条目仍在 KB 里 (但不影响入库脚本, 脚本只新增)
- 存量策略需要按新规则重新上传一份新名条目, 旧条目作为历史保留
- 推荐流程: 1) 改 step5_review_build.py + 命名规则文档; 2) 用 `IMA_策略重命名提示词.md` 跑一遍存量批量重命名 (主人项目根目录的提示词文件)

当前规则: `{year}_{Tcode}_{Tname}_{author}_{title_core}_s{sharpe}.md`, 见 parameters.md。
