[English](README.md) | [简体中文](README_zh.md) | [日本語](README_ja.md) | [한국어](README_ko.md)

# 女性人像提示词导演 Skill

女性人像提示词导演 Skill 是一个面向 AI 生图场景的结构化女性人像提示词生成与视觉导演系统。V1.4.1 会通过唯一风格注册表按需加载单一路由，锁定明确参数或授权参考图主体，并生成完整摄影导演式提示词，或直接生成保留人物身份与产品核心视觉的目标图片。

本项目不是普通提示词合集，而是一个可扩展的女性人像提示词 Skill 框架。

## 项目定位

通过少量输入参数生成完整提示词，并在保留用户明确要求的前提下扩写五官、身形、服装、场景、镜头姿态、光线、滤镜、平台用途和负面约束。默认人物必须是明确成年的女性，输出强调真实摄影质感、克制表达、画面统一和稳定生成。

## 支持风格

- 清纯生活照
- 纯欲曲线生活照
- 都市时尚写真
- 古风仙侠美人图
- 电商服装模特图
- 复古港风写真
- 法式慵懒写真
- 新中式东方写真
- 活力运动写真
- 旅行假日写真
- 影楼精修写真
- 东方丰腴写真
- 清冷仙气古风增强版
- 明媚华贵古风增强版

## 核心能力

- 锁定用户已经填写的参数，只做细化和稳定化补全。
- 根据目标风格按需加载单一路由，避免互相冲突的风格词堆叠。
- 拆解五官、身形、服装、场景、镜头姿态、光线和滤镜模块。
- 将短参数扩写为可拍摄的具体瞬间，避免机械复述和填空式输出。
- 将各模块融合为自然、完整、可直接复制的摄影导演式提示词。
- 为电商图片保留服装展示优先级，为曲线风格保留明确的安全边界。
- 支持授权自拍五官或产品核心视觉锁定后的参考图直接生成。

## 快速开始

将仓库作为 Codex Skill 使用时，可直接调用 `$female-portrait-director`。最简输入示例：

```text
风格：清纯生活照
场景：咖啡馆靠窗座位
服装：白色针织开衫 + 浅色内搭
气质：清纯温柔
画幅：9:16
```

系统将输出参数锁定结果、可直接复制的完整提示词和负面约束。完整调用字段参见 [parameter_schema.md](skill/parameter_schema.md)，示例参见 [usage_examples.md](skill/usage_examples.md)。

## 安装方式

### 使用 npx 一键安装

需要安装包含 `npx` 的 [Node.js](https://nodejs.org/)。执行以下命令，将 Skill 全局安装到 Codex：

```bash
npx skills@latest add liyue-aigc/female-portrait-director -g -a codex -y
```

后续更新已安装的 Skill：

```bash
npx skills@latest update female-portrait-director -g -y
```

### 使用 Git 手动安装

也可以将仓库克隆到 Codex 的 skills 目录。

Windows PowerShell：

```powershell
git clone https://github.com/liyue-aigc/female-portrait-director.git "$env:USERPROFILE\.codex\skills\female-portrait-director"
```

macOS 或 Linux：

```bash
git clone https://github.com/liyue-aigc/female-portrait-director.git "${CODEX_HOME:-$HOME/.codex}/skills/female-portrait-director"
```

重启 Codex 或重新开始一个对话，然后调用：

```text
$female-portrait-director
```

## 示例：从参数到导演式扩写

这个 Skill 不只是复述用户输入。它会保留明确参数，补全缺失的视觉细节，并输出参数锁定结果、导演式模块解析、完整提示词和负面约束。

```text
写真风格：古风仙侠美人图
场景方向：云雾山水间的古风庭院回廊
服装方向：月白色唐风幻想大袖衫 + 轻盈披帛 + 银色刺绣腰封
气质标签：清冷、疏离、仙气
五官方向：古典东方美人脸
身形方向：纤细清瘦身形
镜头方向：轻侧身站姿，半身到大腿构图
光线氛围：冷调柔光
滤镜效果：清冷仙气古风滤镜
画幅比例：9:16
平台用途：角色写真
```

![古风仙侠参数扩写示例](assets/examples/gufeng-director-output.jpg)

## 输出格式

```text
一、参数锁定结果
二、模块解析
三、最终提示词
四、负面约束
```

## 文件结构

```text
.
├── README.md
├── README_zh.md
├── README_ja.md
├── README_ko.md
├── SKILL.md
├── agents/openai.yaml
├── assets/examples/
├── skill/
│   ├── skill.md
│   ├── style-registry.md
│   ├── public_instructions.md
│   ├── parameter_schema.md
│   ├── usage_examples.md
│   ├── core/
│   ├── references/
│   │   ├── director-expansion.md
│   │   └── visual-libraries.md
│   └── routes/
│       ├── commercial/
│       ├── curve/
│       ├── fantasy/
│       ├── fashion/
│       ├── lifestyle/
│       └── oriental/
├── docs/
│   ├── style_guide.md
│   ├── prompt_safety.md
│   ├── versioning.md
│   └── faq.md
└── examples/
```

## 安全边界

文本生图默认使用虚构、明确成年的人物。参考图工作流允许保留用户本人或已授权成年人物的身份，也允许保留用户有权使用的产品视觉。禁止用于未成年人性化、色情裸露、非自愿图像、欺骗性身份内容、骚扰、诽谤、隐私侵犯或其他违法违规用途。详细规则参见 [prompt_safety.md](docs/prompt_safety.md) 和 [DISCLAIMER.md](DISCLAIMER.md)。

## License

本项目使用 [MIT License](LICENSE)。MIT License 允许使用、复制、修改、合并、发布、分发、再许可和销售副本。安全边界属于合理使用说明，不改变 MIT License 的标准授权范围。

## 作者与版本

- 作者：李岳
- 版本：`FEMALE-PORTRAIT-DIRECTOR-V1.4.1`
- 项目：`Female Portrait Prompt Director Skill`
