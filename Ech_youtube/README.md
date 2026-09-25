# Ech_youtube

> Ech_bilibili 的 YouTube 版本。**状态：✅ 已实现并跑通**（单视频端到端 21s 冒烟测试通过，2026-09-18）。

## 安装与自检

在仓库根目录：

```bash
python scripts/install.py                  # 一键：装 ffmpeg + 建 venv + 装依赖 + 自检
python scripts/check_env.py -p youtube     # 只体检本平台
```

**本平台依赖**（见 `requirements.txt`，另有系统级二进制）：

| 依赖 | 安装 |
|---|---|
| `faster-whisper`、`yt-dlp` | `pip install -r Ech_youtube/requirements.txt`（或根 `requirements.txt`） |
| `ffmpeg`（转 wav 必需） | `winget install Gyan.FFmpeg` / `brew install ffmpeg` / `apt install ffmpeg`；或设 `FFMPEG=<路径>` |
| `deno`（解 n-challenge，可选） | https://deno.com 下载后放 `Ech_youtube/bin/`——管线会自动加进 PATH |

管线启动前会自动预检（缺 ffmpeg / 缺依赖 / 缺 Key 直接说人话并 `exit 2`），不会跑到一半才报 traceback。

## 与 Ech_bilibili 的关系

笔记层完全复用 Ech_bilibili 的设计，只替换平台感知层：

| 层 | Ech_bilibili | Ech_youtube |
|----|-------------|-------------|
| 元数据 | view API + 完整浏览器头/cookie（风控对抗） | yt-dlp `extract_info`（官方支持，无需对抗风控） |
| 音频获取 | playurl API 直取 m4s + 截断校验 | yt-dlp `bestaudio/best` → ffmpeg 转 16k 单声道 wav |
| 语言 | 固定中文 | `auto` 自动检测（支持 zh/en/ja 等，可显式指定） |
| ASR 转写 | faster-whisper small/int8（共享同一模型目录，不重复下载） | 同左 |
| 格式整理 | polish.py 中文模式（标点/繁转简/热修词典） | polish.py 双模式：中文同左；其他语言仅标点+大小写，禁改写 |
| 笔记渲染 | 同款 HTML（蓝色 YouTube 主题） | 同款 HTML |
| 批量 | batch_run.py + 卡片墙 | yt_batch.py + 卡片墙（videos.txt 每行一个 URL/id） |

## 从 Bilibili 版继承的稳定性设计

- **三道完整性校验**：转写时长 ≥ 视频时长 95% / polish 字数漂移 ±30% / 缓存命中也复检
- **串行批量铁律**（并发会撞 work 根目录）、OOM 冷却重试（180s×2）
- **trash 回收站**代替直接删除、work 根残留清理（防上一视频产物误回收）
- 代理：默认 `http://127.0.0.1:12000`，可用环境变量 `YT_PROXY` 覆盖（`direct` = 直连）

## 用法

```bash
# 管线一 · 口播/观点类（URL 或裸 id 均可）
python Ech_youtube/yt_pipeline.py https://www.youtube.com/watch?v=jNQXAC9IVRw
python Ech_youtube/yt_pipeline.py jNQXAC9IVRw en        # 显式指定语言

# 访谈/播客类 → 说话人标注 + 中英对照博客笔记
python Ech_youtube/yt_blog.py https://www.youtube.com/watch?v=HUkBz-cdB-k --host "Lex Fridman" --guest "Terence Tao"

# 批量：把 URL/id 每行一个写进 videos.txt，然后
python Ech_youtube/yt_batch.py [输出文件夹名]
```

产出：`runs/<video_id>/笔记.html`（口播类）或 `runs/<video_id>/博客笔记.html`（访谈类），
均含信息卡 + 分节逐字稿 + 原始转写折叠可查证。

## 产物归档命名

新增嘉宾 / 新增视频一律照此落盘，不散落堆放：

```
Ech_youtube/
├── LexFridman-博客笔记/            # 外层：<创作者>-<笔记类型>
│   ├── 01-<标题>.html             # 内层：{NN}-{标题}.html（两位序号，从 01 起，不回收）
│   ├── index.html                 # 卡片墙
│   ├── failed.json                # 失败清单
│   └── batch_log.txt              # 日志
└── runs/<11位 vid>/               # 中间产物（固定名 笔记.html / 博客笔记.html）
```

## 已知限制

- 年龄限制/会员视频需要 cookies（yt-dlp `cookiesfrombrowser` 配置，暂未接）
- 有官方 CC 字幕的视频目前仍走 ASR（后续可加"字幕优先"分支）
- 直播/超长视频未测试
