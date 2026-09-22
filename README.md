# Ech_bilibili（拾音笺）

> 把口播视频"听"成一份可查证的读书笔记。

Ech_bilibili 是视频观看 agent 项目（多平台系列之 Bilibili 版），目标是输入视频链接，输出结构化、可查证的完整内容整理（读书笔记 / 讲义 / 实验报告）。

**多平台设计**：感知层按平台适配，笔记层平台无关；每个平台一个自包含目录，各归各家。GitHub 仓库：`WZAwza050801/Ech_bilibili`（原名 EchoNotes）。

```
视频观看agent编写/            # 仓库根：只放通用文档与各平台目录
├── Ech_bilibili/            # Bilibili 版（管线代码 + runs + 江左道卡卡-读书笔记）
├── Ech_youtube/             # YouTube 版（管线代码 + runs + LexFridman-博客笔记）
├── research/                # 开源项目调研
└── 调研报告-*.md / 方案-*.html # 通用文档
```

| 平台 | 音频/视频获取 | 状态 |
|------|--------------|------|
| Bilibili（[Ech_bilibili/](Ech_bilibili/)） | playurl API 音频直取（完整浏览器头防 412）+ wbi 签名列表拉取 | ✅ 已实现 |
| YouTube（[Ech_youtube/](Ech_youtube/)） | yt-dlp（无 B 站式风控，反而简单） | ✅ 已实现并跑通 |

> B 站适配是本项目最难啃的部分（匿名音频直取、风控对抗、wbi 签名），这些经验沉淀在 `Ech_bilibili/` 中；YouTube 版只需替换获取层，ASR/polish/笔记层全部复用。

## 三类内容管线（设计）

| 管线 | 输入形态 | 输出 | 状态 |
|------|---------|------|------|
| 一 · 口播/观点类 | 播客、观点、推荐视频（纯音频） | 读书笔记 + 整理版逐字稿 | ✅ 已落地 |
| 二 · 课程类 | 数学/学术讲座 | LaTeX 可阅读讲义 | 设计完成，待启动 |
| 三 · 实操教程类 | PS/绘画/剪辑/开发教程 | 讲义 + 实验报告 + 复刻作品 | 设计完成，待启动 |

详细设计见 `方案-三类视频内容分管线设计.html`，开源项目源码级调研见 `调研报告-*.html/md`。

## 管线一：口播视频 → 读书笔记

```bash
python Ech_bilibili/pipeline1.py BV1GbNH6hE8f
```

一条命令全自动：**B站音频直取 → ffmpeg 转wav → faster-whisper 本地转写 → LLM 格式整理 → 读书笔记 HTML**（含信息卡、分节逐字稿、原始转写折叠查证）。

### 架构与关键实现

- **B站音频直取**（绕过 yt-dlp 412）：直接调 `api.bilibili.com/x/player/playurl?fnval=16`。关键点是**完整浏览器请求头 + 完整 cookie 组**（buvid3/buvid4/b_nut 等 8 项）——极简头（单个伪造 buvid3）会被风控 412 拦截；同时禁用系统代理直连。
- **本地 ASR**：faster-whisper small/int8（CPU 约 2.3x 实时），`vad_filter=True` + `condition_on_previous_text=False` 防幻觉复读。
- **格式整理（polish 模块）**：便宜的 LLM（deepseek-chat）只做加标点/繁转简/修有把握的同音错字，prompt 硬约束禁改写；`[n]` 序号一一对应 + 字数漂移校验；**hotfix.json 热修词典双端应用**（输入端预处理 + 输出端后处理）管已确认 ASR 错字，词典可持续积累。
- **逐段查证**：笔记 HTML 底部折叠保留原始机器转写全文，整理稿与原始稿可逐句对照。

### 目录

```
Ech_bilibili/
├── pipeline1.py            # 总控：BV号 → 笔记.html（带缓存跳过 + 三道完整性校验）
├── batch_run.py            # 批量模式：UP主全部视频 → 笔记卡文件夹 + 卡片墙（断点续跑 + OOM冷却重试）
├── transcribe_local.py     # faster-whisper 本地转写（int8 + cpu_threads=4）
├── polish.py               # LLM 格式整理模块（禁改写约束 + 字数漂移校验）
├── hotfix.json             # ASR 错字热修词典（双端应用）
├── fetch_list.py           # UP主视频列表（wbi 签名直连版）
├── fetch_list_retry2.cjs   # UP主视频列表（playwright 驱动系统 Edge + 风控退避重试版，匿名可行方案）
├── cleanup_fake.py         # 假产物清理（按转写时长完整性比对）
└── runs/<BV>/              # 每个视频的产物（meta/转写/整理稿/笔记）
```

### 稳定性设计（血泪经验）

- **三道完整性校验**：转写时长 ≥ 视频时长 95%（防截断音频）、polish 字数漂移 ±30%（防 LLM 幻觉）、缓存命中也复检（防历史假产物泄漏）
- **产物回收站**：校验失败的产物移入 `runs/_trash/` 而非直接删除，可追溯
- **OOM 防御**：转写限线程（ctranslate2 workspace 峰值问题）、批量模式遇内存错误自动冷却重试
- **串行铁律**：批量任务必须串行（共享中转文件，并发互踩）

### 依赖

- Python 3.10+，`faster-whisper`（模型自动从 `models/faster-whisper-small` 加载，首次需下载到该目录）
- `ffmpeg`（PATH 中可用）
- DeepSeek API Key：通过环境变量 `DEEPSEEK_API_KEY` 提供（`polish.py` 中按需改读取方式，仓库不含任何密钥）

## 路线图

- [x] 管线一端到端全自动（一条命令出笔记）
- [x] 批量模式：UP 主全部视频 → 笔记卡文件夹 + 卡片墙索引
- [x] 114 个视频批量实测（含风控对抗、假产物防御、OOM 修复全流程）
- [ ] YouTube 平台适配
- [ ] 管线二：课程视频 → LaTeX 讲义（Pix2Text 公式 OCR）
- [ ] 管线三：实操教程 → 复刻 + 实验报告（A/B/C 可执行性分级）
- [ ] CC 字幕优先策略（有官方字幕时免 ASR，零错字）
