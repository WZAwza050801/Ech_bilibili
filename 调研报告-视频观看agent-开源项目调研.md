# 「视频观看 Agent」开源项目调研报告

> 调研时间：2026-09-16 | 目标：调研 GitHub 上已有的「B站视频 → 完整内容整理/文章笔记」相关项目，为自研 agent 找参考、找轮子、找差异化空间。

---

## 一、结论先行（TL;DR）

1. **B站视频总结类项目非常多**（几十个），但 90% 的定位是「省流神器 / AI课代表」——即"摘要 + 要点"，**不是你要的"完整内容整理"**。
2. 主流技术路线基本收敛为：**下载 → 字幕优先直取（B站AI字幕）→ ASR兜底（Whisper）→ LLM 总结**。视觉通道（画面理解）大多数项目是缺失或装饰性的。
3. **离你的需求最近的项目**：
   - `Librarier-f/video-to-article-skill`（视频→文章→公众号文案，但纯字幕驱动、无画面理解）
   - `xiaohui5206/let-ai-read-video`（双通道：转写+场景感知抽帧+时间戳对齐，本地化做得最认真）
   - `KIRVO-REPORTING/video-to-notes`（工程化最完整：字幕优先+时间戳回溯+报告落盘）
4. **空白点 = 你的差异化机会**：「转写 + 画面双通道深度理解 → 分段分章 → 写作模型产出公众号推文级的完整文章」这条完整链路，目前没有现成项目做到，但各环节的轮子都是现成的，可以拼装。

---

## 二、项目清单（按类别）

### A. B站视频总结类（定位=省流摘要）

| 项目 | Stars | 一句话定位 | 可借鉴点 |
|---|---|---|---|
| [JimmyLv/BibiGPT-v1](https://github.com/JimmyLv/BibiGPT-v1) | 6.2k | 最知名的B站AI总结（原BiliGPT），Next.js 全栈 | 产品形态参考；多平台接入架构 |
| [lxfater/BilibiliSummary](https://github.com/lxfater/BilibiliSummary) | 724 | Chrome 扩展，浏览器内总结 | B站字幕获取方式 |
| [Well2333/nonebot-plugin-bilichat](https://github.com/Well2333/nonebot-plugin-bilichat) | 264 | QQ机器人插件，总结B站/YouTube | 字幕+ASR 双路策略 |
| [LDJ-creat/video-helper](https://github.com/LDJ-creat/video-helper) | 49 | 思维导图+总结，支持B站/抖音/本地；**LLM引导关键帧提取** | 关键帧提取思路、云ASR（DashScope/火山）配置 |
| [jackwener/bilibili-summary](https://github.com/jackwener/bilibili-summary) | 22 | B站总结 CLI，带 ASR | 简洁的 pipeline 参考 |
| [Cansiny0320/bilibili-video-summary-agent](https://github.com/Cansiny0320/bilibili-video-summary-agent) | 9 | LLM CLI，字幕或音频转写双路 | 双路 fallback 写法 |
| [LiuMashiro/Bilibili-Subtitle-Extraction-...](https://github.com/LiuMashiro/Bilibili-Subtitle-Extraction-AI-Summary-Ad-Skipping) | 6 | 字幕提取+总结+广告识别+评论区舆情 | 评论维度可加 |

### B. 视频 → 笔记/文章（离需求最近）

| 项目 | Stars | 一句话定位 | 可借鉴点 |
|---|---|---|---|
| [KIRVO-REPORTING/video-to-notes](https://github.com/KIRVO-REPORTING/video-to-notes) | 107 | **本地优先 CLI**：字幕优先、Whisper兜底、带时间戳的摘要报告、可发 Notion/Obsidian | 工程化模板：转写与摘要绑定时间戳、可回溯、报告落盘 |
| [Librarier-f/video-to-article-skill](https://github.com/Librarier-f/video-to-article-skill) | 32 | **视频→文章 skill**：下载字幕→翻译→整理成文→输出公众号/小红书/口播稿，5种排版 | **唯一直接输出"公众号文章"的项目**；输出层设计直接可抄；但纯字幕驱动，无画面理解 |
| [liang121/video-summarizer](https://github.com/liang121/video-summarizer) | 54 | 1800+平台下载，输出MP4/MP3/字幕 | 下载层 |
| [Alliskyline2020/podcast-digester](https://github.com/Alliskyline2020/podcast-digester) | 9 | 播客/视频蒸馏：转录·分章·摘要·五类亮点·双语字幕，多LLM可插拔 | **分章（chaptering）思路**、DeepSeek/OpenAI可插拔 |
| [LjyYano/skill-pack](https://github.com/LjyYano/skill-pack) | 44 | video-to-note 等 skill 合集 | skill 组织方式 |

### C. 视觉感知层（分帧 + 多模态"看"视频）

| 项目 | Stars | 一句话定位 | 可借鉴点 |
|---|---|---|---|
| [jordanrendric/claude-video-vision](https://github.com/jordanrendric/claude-video-vision) | 1.3k | Claude Code 插件：ffmpeg抽帧 + 音频后端(Gemini/Whisper/OpenAI)，"**感知层而非解释层**" | 架构哲学：把帧+带时间戳转写喂给模型，让模型自适应调 fps/时间段/分辨率 |
| [xiaohui5206/let-ai-read-video](https://github.com/xiaohui5206/let-ai-read-video) | 7 | **双通道本地视频阅读 skill**：faster-whisper GPU转写 + 场景感知抽帧，时间戳对齐(t=MM:SS)，**证据驱动补帧**，B站客户端缓存免下载 | ⭐ 全场最贴近你说的"分帧分段+语音对齐"：场景检测+均匀补点、转写与帧 PTS 对齐、预算控制（首轮2fps/100帧上限，局部补帧最高4fps）、多P合集选集 |
| [maim010/openclaw-video-vision](https://github.com/maim010/openclaw-video-vision) | 20 | 每5秒抽帧（40分钟视频约117帧）+ 视觉AI结构化总结 | 均匀抽帧+时间戳引用的简单做法 |

### D. 底层工具轮子（直接用，不用自己写）

| 工具 | Stars | 用途 |
|---|---|---|
| [nilaoda/BBDown](https://github.com/nilaoda/BBDown) | 13.9k | B站下载（画质最好，含弹幕/章节/多P），需要登录态时用 |
| [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) | — | 通用下载 + **可直接拉B站AI/CC字幕**（需 SESSDATA cookie） |
| faster-whisper | — | 本地 ASR 兜底（GPU 下 1小时视频 3-5 分钟，参考 let-ai-read-video 实测） |
| ffmpeg + PySceneDetect | — | 抽帧 + 场景切换检测（避免暴力等间隔抽帧浪费） |

---

## 三、关键发现 & 空白点分析

**现有项目的共同短板：**

1. **摘要 ≠ 完整内容整理**。几乎所有项目把 LLM 输出控制在几百字要点/大纲，没有人做"分段消费全部转写 → 产出与视频结构一一对应的完整文章"。你的需求（完整整理、推文级）本质是**信息保留率**要求高，这需要分段 map-reduce 式处理，而不是一把梭摘要。
2. **视觉通道普遍缺失**。字幕/ASR 能覆盖"说了什么"，覆盖不了"画面上有什么"（代码演示、图表、评测对比画面、操作步骤）。只有 claude-video-vision 和 let-ai-read-video 认真做了画面通道。
3. **时间对齐只有少数项目认真做**。let-ai-read-video 的"转写 PTS ↔ 帧时间窗 ↔ 证据驱动补帧"是目前最完整的时间轴对齐方案。
4. **B站的特殊性是优势**：大部分B站视频有官方 CC 字幕或 AI 字幕，yt-dlp 带 SESSDATA 就能直取，**很多视频根本不需要跑 ASR**。ASR 只做兜底，能省大量时间成本。

**推导出的自研架构（轮子拼装方案）：**

```
[B站链接]
   → 下载层: yt-dlp/BBDown（字幕直取优先，SESSDATA；视频流按需下载）
   → 语音层: CC/AI字幕直取 → 无字幕时 faster-whisper 兜底 → 带时间戳转写
   → 画面层: ffmpeg + 场景检测抽帧（首轮限预算，证据不足局部补帧）
   → 理解层: 多模态模型（Gemini / 豆包 / Kimi）分段处理「转写片段 + 对应时间窗帧」→ 分段结构化笔记（map）
   → 写作层: 写作模型（DeepSeek/GLM 等）把分段笔记合并成章（reduce）→ 按推文模板产出完整文章
   → 输出层: Markdown + 公众号格式（可接你 D 盘已有的公众号工具链）
   全程时间戳贯穿，文中引用可回溯到视频 t=MM:SS
```

这个架构里，每一层都有上面项目可以直接抄的实现，组合本身（双通道深度理解 + map-reduce 完整成文 + 公众号输出）就是新东西。

---

## 四、建议下一步

1. **clone 拆解三个项目**：`let-ai-read-video`（抽帧+对齐+预算控制）、`video-to-notes`（工程化+报告落盘）、`video-to-article-skill`（公众号输出模板）。
2. **先做最小 PoC**：挑一个有字幕的B站视频，跑通「字幕直取 → 分段 → 多模态分段笔记 → 合并成文」全链路，验证输出质量是不是你要的"完整整理"。
3. **再补视觉通道**：接入场景感知抽帧，对比有/无画面信息时文章质量差异，决定画面层的投入程度。
