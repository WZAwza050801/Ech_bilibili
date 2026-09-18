# 拾音笺 EchoNotes

> 把 B 站口播视频"听"成一份可查证的读书笔记。

EchoNotes 是一个视频观看 agent 项目，目标是输入 B 站视频链接，输出结构化、可查证的完整内容整理（读书笔记 / 讲义 / 实验报告）。

## 三类内容管线（设计）

| 管线 | 输入形态 | 输出 | 状态 |
|------|---------|------|------|
| 一 · 口播/观点类 | 播客、观点、推荐视频（纯音频） | 读书笔记 + 整理版逐字稿 | ✅ 已落地 |
| 二 · 课程类 | 数学/学术讲座 | LaTeX/PDF 讲义 + 音画证据 | 首版已实现，待真实课程验收 |
| 三 · 实操教程类 | PS/绘画/剪辑/开发教程 | 讲义 + 实验报告 + 复刻作品 | 设计完成，待启动 |

详细设计见 `方案-三类视频内容分管线设计.html`，开源项目源码级调研见 `调研报告-*.html/md`。

## 管线一：口播视频 → 读书笔记

```bash
python pipeline1.py BV1GbNH6hE8f
```

一条命令全自动：**B站音频直取 → ffmpeg 转wav → faster-whisper 本地转写 → LLM 格式整理 → 读书笔记 HTML**（含信息卡、分节逐字稿、原始转写折叠查证）。

### 架构与关键实现

- **B站音频直取**（绕过 yt-dlp 412）：直接调 `api.bilibili.com/x/player/playurl?fnval=16`。关键点是**完整浏览器请求头 + 完整 cookie 组**（buvid3/buvid4/b_nut 等 8 项）——极简头（单个伪造 buvid3）会被风控 412 拦截；同时禁用系统代理直连。
- **本地 ASR**：faster-whisper small/int8（CPU 约 2.3x 实时），`vad_filter=True` + `condition_on_previous_text=False` 防幻觉复读。
- **格式整理（polish 模块）**：便宜的 LLM（deepseek-chat）只做加标点/繁转简/修有把握的同音错字，prompt 硬约束禁改写；`[n]` 序号一一对应 + 字数漂移校验；**hotfix.json 热修词典双端应用**（输入端预处理 + 输出端后处理）管已确认 ASR 错字，词典可持续积累。
- **逐段查证**：笔记 HTML 底部折叠保留原始机器转写全文，整理稿与原始稿可逐句对照。

### 目录

```
work/pipeline1/
├── pipeline1.py        # 总控：BV号 → 笔记.html（带缓存跳过）
├── transcribe_local.py # faster-whisper 本地转写
├── polish.py           # LLM 格式整理模块
├── hotfix.json         # ASR 错字热修词典（双端应用）
└── runs/<BV>/          # 每个视频的产物（meta/转写/整理稿/笔记）
```

### 依赖

- Python 3.10+，`faster-whisper`（模型自动从 `models/faster-whisper-small` 加载，首次需下载到该目录）
- `ffmpeg`（PATH 中可用）
- DeepSeek API Key：通过环境变量 `DEEPSEEK_API_KEY` 提供（`polish.py` 中按需改读取方式，仓库不含任何密钥）

## 路线图

- [x] 管线一端到端全自动（一条命令出笔记）
- [ ] 批量模式：UP 主全部视频 → 笔记卡文件夹 + 卡片墙索引
- [x] 管线二首版：混合抽帧 + 多模态公式识别 + map-reduce + LaTeX/PDF
- [ ] 管线二真实课程验收与短暂板书自动补帧
- [ ] 管线三：实操教程 → 复刻 + 实验报告（A/B/C 可执行性分级）

## 管线二：课程视频 → LaTeX/PDF 讲义

支持 B 站 BV/完整视频链接（含分 P）和本地视频；复用本地 Whisper，
增加实际 PTS 抽帧、板书识别、知识块整理、公式视觉复查与中文 PDF 编译。
每个知识块保留证据 ID，附录可查看原始板书帧。

```powershell
python -m work.pipeline2.pipeline2 doctor
python -m work.pipeline2.pipeline2 run '实际BV号或本地视频路径' --secrets '外部密钥文件路径'
```

依赖、模型配置、缓存与归档方式、测试命令见 [管线二使用说明](work/pipeline2/README.md)。
所有课程产物均为待核验初稿；编译成功不等于数学正确。
