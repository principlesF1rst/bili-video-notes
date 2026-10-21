---
name: bili-video-notes
description: Use when 用户给出B站(bilibili)视频链接或BV号，想把视频转成文字笔记、提取字幕、总结视频内容、生成带Mermaid图表的结构化Markdown学习笔记；也适用于把本地音视频文件转写成笔记
---

# B站视频转结构化笔记

## 概述

把 B 站视频变成**不丢内容**的学习笔记：完整字幕存档（transcript.md）+ AI 结构化笔记（notes.md，含时间锚点和 Mermaid 图）。核心原则：**笔记是"重组 + 索引"，不是"压缩"**——所有知识点、数据、结论、例子必须保留，只去掉寒暄和重复。

合集类视频的最终交付物是**章节合并版**：分集文件统一放 `<课程目录>/中间产物/`，按章节组装出的最终笔记放 `<课程目录>/笔记/`（见工作流程第 7 步）。

## 启动前：确认用户意图

用户发 B 站链接 ≠ 要转写，也可能只是想讨论视频内容。开工前先判断意图：

- **意图明确**（消息里带"转笔记/整理笔记/提取字幕/总结/做纪要/字幕文本"等明确诉求）→ 不问，直接进入工作流程
- **只丢了链接或 BV 号、没说目的** → 先用一句话确认，例如："收到链接，想让我怎么处理？① 转成结构化笔记 ② 只提取字幕 ③ 总结要点 ④ 其他"。用户选择后再执行，选"其他/只是聊聊"则不启动本流程
- 确认时只问一句，不要附带流程说明或环境介绍

## 环境

下文中两个路径占位符：

- `<SKILL_DIR>` = 本 SKILL.md 所在目录（即 skill 安装位置）
- `<TOOLS_DIR>` = 工具目录，默认 `<SKILL_DIR>/tools/`，可用环境变量 `BILI_NOTE_TOOLS` 指到任意位置

| 组件 | 约定位置 |
|---|---|
| skill 脚本 | `<SKILL_DIR>/scripts/` |
| yt-dlp / ffmpeg / whisper-venv / 缓存 / cookie | `<TOOLS_DIR>` 下 |

转写脚本必须用 whisper-venv 的 python 运行（Windows 为 `Scripts/python.exe`，macOS/Linux 为 `bin/python`）；其余脚本用系统 `python` 即可。首次使用/换机器先跑第 0 步。

## 工作流程

### 0. 环境检查（只在首次/异常时运行，不是每条链接都跑）

**触发时机（满足其一才执行本步，平时直接进第 1 步）：**
- 本机第一次使用本 skill
- 某条命令执行失败，怀疑工具缺失/损坏
- 用户更换了机器或工具目录

```bash
python <SKILL_DIR>/scripts/doctor.py
```

完整检查通过后会写入标记文件 `tools\.env_checked`，之后 doctor 秒过；`--force` 可强制重新完整检查。

**呈现规则（重要）：**
- **第一次使用**：把缺失项与体积、faster-whisper 的作用与可选性、CUDA 加速选项、cookie 配置引导完整呈现给用户，征得其逐项决定后再安装
- **后续使用**：不再重复展示任何安装/环境内容，直接开始处理链接；只有命令失败或标记失效时才重新检查并向用户说明

有缺失时必须告知用户要下载什么、体积多大，征得同意后再安装：

| 内容 | 体积 | 说明 |
|---|---|---|
| yt-dlp | ≈17MB | 下载音频/视频（必需） |
| ffmpeg | ≈190MB | 音视频处理（必需） |
| faster-whisper 及依赖（可选） | ≈200MB | 无官方字幕时的兜底本地转写；不装则无法处理无字幕视频 |
| whisper small 模型（可选） | ≈460MB | 装了 faster-whisper 后首次转写时自动下载 |
| CUDA 运行库（可选） | ≈1GB | faster-whisper 的加速项，有 N 卡且用户同意才装 |

**faster-whisper 不是必装项，安装前必须先向用户解释清楚作用，由其决定：**

> faster-whisper 是本地语音识别工具（OpenAI Whisper 的高性能实现），作用是把音频转成带时间戳的文字。它只在"视频没有官方字幕"时用得上——如果视频本身有字幕轨且已配置 B 站 cookie，直接抓字幕即可，完全用不到它。

- 用户确认需要处理无字幕视频 → 安装（依赖 ≈200MB + 模型 ≈460MB 首次自动下载）
- 用户只处理有字幕视频、或不想装 → 跳过；之后遇到无字幕视频时如实告知无法处理

**确定要装之后，再提示加速选项（同样由用户决定）：**

> faster-whisper 默认 CPU 即可运行（int8），CUDA 只是可选加速器：有 N 卡可额外装 ≈1GB 运行库，速度提升约 3~5 倍。

- 启用：往 whisper-venv 里装 `nvidia-cublas-cu12` + `nvidia-cudnn-cu12`，转写自动走 `cuda/float16`
- 不启用/无 N 卡：CPU（`--device cpu --compute int8`），不装 CUDA 库

所有工具统一装进 `<TOOLS_DIR>`（已在 .gitignore 排除），不污染系统全局环境。

### 1. 获取字幕（优先官方字幕）

```bash
python <SKILL_DIR>/scripts/fetch_subtitle.py "<BV号或链接>" -o <输出根目录>
```

- 成功（退出码 0）：生成 `<输出根目录>/<视频标题>/transcript.md`，脚本最后一行打印 `TRANSCRIPT=路径`
- 输出根目录默认用**当前工作目录**（用户在哪个知识库目录下就跑在哪）
- 多 P 视频默认全部抓取；只要某一 P 用 `--page N`

**重要：B站字幕现在必须登录才能拿到（匿名调用永远返回空）。** 首次使用时引导用户做一次配置：
1. 浏览器登录 bilibili.com，按 F12 → 应用/Application → Cookies → `https://www.bilibili.com`
2. 复制 `SESSDATA` 的值，写入文件 `<TOOLS_DIR>/bili_cookie.txt`（只写值本身即可）
3. 脚本会自动读取该文件；也可用 `--cookie "SESSDATA=xxx"` 或环境变量临时传入

没有 cookie 就直接走第 2 步 whisper 降级（零配置可用，只是慢）。
注意：`yt-dlp --cookies-from-browser` 在浏览器开着时会因数据库锁定失败，不作为默认方案。

### 2. 无官方字幕时降级到 whisper（退出码 2）

```bash
python <SKILL_DIR>/scripts/download_audio.py "<链接>"
<TOOLS_DIR>/whisper-venv/Scripts/python.exe <SKILL_DIR>/scripts/transcribe.py <TOOLS_DIR>/cache/audio.m4a -o <笔记目录>/transcript.md --title "<视频标题>"
rm -f <TOOLS_DIR>/cache/audio.m4a   # 转写成功后立即删除音频
```

- 音频只作为中转放进缓存目录 `<TOOLS_DIR>/cache/`，**转写成功后必须删除**——笔记目录里最终只有 transcript.md 和 notes.md 两个纯文本文件，不留音视频
- 默认 `small` 模型（首次使用自动从 hf-mirror 下载）；赶时间用 `--model base`，求质量用 `--model medium`
- 有 N 卡且装了 CUDA 运行库时，脚本自动检测走 `cuda/float16`；显存不够或跑大型模型报错时，手动 `--device cpu --compute int8` 回退
- 长视频转写较慢，放后台跑

### 3. AI 结构化（你自己做，不是脚本做）

读 transcript.md，产出同目录的 notes.md。规则：

**防丢内容（必须遵守）：**
- transcript.md 完整保留，notes.md 只做重组和索引，**每个章节必须写时间锚点**：`> ⏱ 开始-结束`（单 P 可省略 P 号；多 P 写 `> ⏱ P2 03:00-09:10`）
- 保留所有知识点、定义、数据、结论、例子、操作步骤；只删口头禅、寒暄、纯重复
- 转录超过约 8000 字就按时间段分块处理（每次读一段，逐章追加写入 notes.md），最后统一补全局结构图和术语表

**notes.md 结构模板：**

```markdown
# 《视频标题》学习笔记
> 来源：https://www.bilibili.com/video/BVxxx · UP主 · 总时长
> 完整转录：[[transcript]]

## 全局结构
（mermaid mindmap，把全篇知识体系画成树状图）

## 一、章节标题
> ⏱ 00:00-08:32

（详尽要点、定义、步骤、例子……）

（仅当内容是结构/流程/关系/时序时，配 mermaid 图）

## 术语表
| 术语 | 说明 |
```

### 4. 配图规则（只看字幕，不截视频帧）

不做视频抽帧/图像识别。是否配图完全由你根据 transcript 文本语义判断；图必须能从字幕内容追溯出来，**不得凭常识脑补字幕里没有的节点和连线**。

**流程图触发条件（满足才配 `flowchart TD`）：**
- 出现明确顺序词：首先/然后/接着/再/最后、步骤一/二/三、先…再…、当…时就…
- 且能整理出 ≥3 个连续步骤或判断分支
- 例：安装流程、加锁流程、redo log 写入流程、ReadView 可见性判断流程

**结构/关系图触发条件（满足才配 `mindmap` / `classDiagram` / `flowchart` / `erDiagram`）：**
- 出现组成/包括/分为/由…构成/架构/模块/依赖/调用/包含/上下游/版本链/主从等关系表述
- 且涉及 ≥3 个实体，且实体间关系在字幕里说清楚了
- 知识体系/章节框架用 `mindmap`；组件或模块关系用 `classDiagram`/`flowchart`；表关系用 `erDiagram`

**时序图触发条件：** 多个角色/组件之间有明确“谁先发、谁响应、谁提交/回滚”的交互顺序，配 `sequenceDiagram`。

| 内容特征 | 图类型 |
|---|---|
| 知识体系、分类 | `mindmap`（全局必配一个，可只按章节标题整理） |
| 步骤、流程、判断分支 | `flowchart TD` |
| 概念/组件/模块关系 | `classDiagram` 或 `flowchart` |
| 表/实体关系 | `erDiagram` |
| 交互、调用时序 | `sequenceDiagram` |
| 演进、历史 | `timeline` |

- 每章最多 1~2 个图；纯叙述、定义罗列、口语例子不硬配
- 拿不准关系是否成立时：不画图，只写文字要点；不要把图画成文字段落的重复
- Mermaid 语法红线：节点文字里有括号/逗号/冒号等一律用引号包起来（`A["文字(含括号)"]`）；mindmap 里避免半角括号；节点 id 只用英文，显示文字放引号里

### 5. 覆盖校验（写完笔记必须跑）

```bash
python <SKILL_DIR>/scripts/check_coverage.py <transcript.md> <notes.md>
```

- 报"未覆盖时间段"→ 回 transcript.md 补读该段，把遗漏内容补进 notes.md 对应章节，再跑一遍直到通过
- "术语提醒"列出转录里出现但笔记里没有的术语，逐个确认：重要就补进笔记，确实无关紧要（如口头禅误识别）才跳过

### 6. 收尾

告诉用户：笔记路径、共几章、校验是否通过、whisper 转写的视频提醒一句"AI 转写可能有个别错字"。

### 7. 章节合并与最终目录（合集的标准收尾）

**章节合并版才是给用户看的最终笔记；一集一集的分集文件是中间产物。** 合集处理完（或新增若干集）后必须执行本步。

标准目录结构：

```text
<课程目录>/
├── 中间产物/          # 分集：P{n}-标题/transcript.md + notes.md
├── 笔记/              # 最终版：章节合并 md
└── chapters.json      # 章节划分配置
```

操作规则：
1. 分集目录统一放 `中间产物`。发现课程目录根下散落 `P*` 文件夹时，先全部移入 `中间产物` 再合并
2. 在 `<课程目录>/chapters.json` 里维护章节划分：按分 P 标题里的主题分段（如"基础-SQL"、"进阶-索引"、"进阶-锁"），支持连续区间 `{"from":66,"to":88}` 或零散列表 `{"episodes":[57,58]}`
3. 运行通用合并脚本（纯组装不改写分集内容，只调整标题层级；幂等，可反复重跑）：
   ```bash
   python <SKILL_DIR>/scripts/merge_chapters.py <课程目录>
   ```
4. 脚本会重新生成 `笔记/<章节>.md`（含章节目录和分集/转录跳转链接），并校验所有相对链接；**失效链接或缺失分集必须以 0 为目标处理完再交付**
5. 新增分集时：直接放进 `中间产物`，更新 `chapters.json` 的集数范围，重跑合并脚本即可

## 常见错误

| 问题 | 对策 |
|---|---|
| fetch 退出码 2（无官方字幕） | 走第 2 步 whisper 降级 |
| 字幕列表为空 | B站字幕必须登录：确认 `bili_cookie.txt` 已配好且 SESSDATA 没过期；仍为空说明该视频真没有字幕轨，走 whisper |
| B站 API 412 | 触发风控，加 `--cookie` 重试；频繁出现时停几分钟再用 |
| whisper-venv python 报 DLL 错误 | 需装 VC++ 运行库；或退而求其次只用官方字幕路径 |
| 转写报 `metadata_errors` TypeError | venv 里 PyAV 版本太新，跑 `pip install "av<16"` 降级（本机已处理） |
| 转写结果为空 | VAD 判定无语音——宣传片/音乐类视频属正常，如实告知用户"该视频几乎没有语音内容"；若视频明显有人声再排查 |
| 转写全是重复短句（如"字幕byXXX"） | whisper 在纯音乐/噪声上的幻觉，同样说明该视频无有效语音 |
| 模型下载 SSL/连接失败 | 脚本已内置：默认走 hf-mirror 国内镜像且对其直连绕过代理。仍失败则换小模型 `--model tiny`，或稍候重试（本机代理偶尔会断） |
| 文件名非法字符 | 脚本已自动替换，不用处理 |
| 会员/付费视频 | 两个脚本都支持 `--cookie`；下载不了就如实告诉用户无法处理 |
