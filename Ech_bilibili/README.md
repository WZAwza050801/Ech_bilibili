# Ech_bilibili

> 视频观看 agent · **Bilibili 版**（管线一：口播/观点类 → 读书笔记）。**状态：✅ 已实现并跑通**（114 个视频批量实测收官）。

## 安装与自检

在仓库根目录：

```bash
python scripts/install.py                # 一键：装 ffmpeg + 建 venv + 装依赖 + 自检
python scripts/check_env.py -p bili      # 只体检本平台
```

**本平台依赖**（见 `requirements.txt`，另有系统级二进制）：

| 依赖 | 安装 |
|---|---|
| `faster-whisper`（本地转写） | `pip install -r Ech_bilibili/requirements.txt`；也可独立 venv 装 `requirements-asr.txt` |
| `ffmpeg`（转 wav 必需） | `winget install Gyan.FFmpeg` / `brew install ffmpeg` / `apt install ffmpeg`；或设 `FFMPEG=<路径>` |
| whisper 模型 | 优先 `models/faster-whisper-small`；目录不在时回退 HF 模型名 `small`（首次联网下载） |
| DeepSeek API Key | 环境变量 `DEEPSEEK_API_KEY`，回退本机密码书（不配则跳过 polish 润色） |

取流/请求部分只用 Python 标准库（urllib / json / sqlite3），不带重型依赖。

管线启动前会自动预检（缺 ffmpeg / 缺依赖 / 缺 Key 直接说人话并 `exit 2`），不会跑到一半才报 traceback。

## 用法

```bash
# 单视频（BV 号）
python Ech_bilibili/pipeline1.py BV1GbNH6hE8f

# 批量：UP 主全部视频 → 笔记卡文件夹 + 卡片墙（断点续跑 + OOM 冷却重试）
python Ech_bilibili/batch_run.py
```

产出：`runs/<BV号>/笔记.html`（信息卡 + 分节整理稿 + 原始转写折叠可查证），
批量产物归档到 `<创作者>-读书笔记/{NN}-<标题>.html` + `index.html` 卡片墙。

## 架构与关键实现

- **B站音频直取**（绕过 yt-dlp 412）：直接调 `api.bilibili.com/x/player/playurl?fnval=16`。关键点是**完整浏览器请求头 + 完整 cookie 组**（buvid3/buvid4/b_nut 等 8 项）——极简头（单个伪造 buvid3）会被风控 412 拦截；同时禁用系统代理直连。
- **本地 ASR**：faster-whisper small/int8（CPU 约 2.3x 实时），`vad_filter=True` + `condition_on_previous_text=False` 防幻觉复读。
- **格式整理（polish 模块）**：便宜的 LLM（deepseek-chat）只做加标点 / 繁转简 / 修有把握的同音错字，prompt 硬约束禁改写；`[n]` 序号一一对应 + 字数漂移校验；`hotfix.json` 热修词典双端应用。
- **风控对抗**：`fetch_list.py`（wbi 签名直连）与 `fetch_list_retry2.cjs`（playwright 驱动系统 Edge + 退避重试）双方案。

## 稳定性设计（血泪经验）

- **三道完整性校验**：转写时长 ≥ 视频时长 95% / polish 字数漂移 ±30% / 缓存命中也复检
- **产物回收站**：校验失败的产物移入 `runs/_trash/` 而非直接删除，可追溯
- **OOM 防御**：转写限线程、批量模式遇内存错误自动冷却重试
- **串行铁律**：批量任务必须串行（共享中转文件，并发互踩）

## 目录

```
Ech_bilibili/
├── pipeline1.py            # 总控：BV号 → 笔记.html（缓存跳过 + 三道校验 + 启动预检）
├── batch_run.py            # 批量：UP主全部视频 → 笔记卡文件夹 + 卡片墙
├── transcribe_local.py     # faster-whisper 本地转写（int8 + cpu_threads=4）
├── polish.py               # LLM 格式整理（禁改写约束 + 字数漂移校验）
├── hotfix.json             # ASR 错字热修词典（双端应用）
├── fetch_list.py           # UP主视频列表（wbi 签名直连版）
├── fetch_list_retry2.cjs   # UP主视频列表（playwright 驱动系统 Edge + 风控退避重试版）
├── cleanup_fake.py         # 假产物清理（按转写时长完整性比对）
├── requirements.txt        # 平台依赖声明
├── models/                 # whisper 模型（两平台共享，不进仓库）
├── runs/<BV>/              # 每个视频的中间产物
├── dev/                    # 一次性探路脚本留档（非产品代码，可整目录删掉）
└── 江左道卡卡-读书笔记/      # 产出：{NN}-<标题>.html + index.html + failed.json + batch_log.txt
```

标题取名走 `batch_run.py::safe_name()`：除 Windows 非法字符 `\ / : * ? " < > |` 与空白外，
**`#` 和 `%` 也会被替换成 `_`**（`#` 在 URL 里是锚点分隔符，会让卡片墙链接被截断成 404）。
截断 60 字，序号从 01 起不回收。

## 环境变量

全部可选，默认值自动适配脚本位置；同时接受 `ECHONOTES_*` 与 `ECH_*` 两种命名。
完整表格见[仓库根 README](../README.md#环境变量参考)。
