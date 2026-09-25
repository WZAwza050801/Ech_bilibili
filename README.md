# Ech_bilibili（拾音笺）

> 把 B 站视频**"听"成读书笔记、"学"成 LaTeX 讲义、"做"成可运行的复刻作品。

Ech_bilibili 是视频观看 agent 项目（多平台系列之 Bilibili 版），目标是输入视频链接，输出结构化、可查证的完整内容整理（读书笔记 / 讲义 / 实验报告）。

**多平台设计**：感知层按平台适配，笔记层平台无关；每个平台一个自包含目录，各归各家。GitHub 仓库：`WZAwza050801/Ech_bilibili`（原名 EchoNotes）。

```
视频观看agent编写/            # 仓库根：只放通用文档、脚本与各平台目录
├── Ech_bilibili/            # Bilibili 版（管线代码 + runs + 江左道卡卡-读书笔记）
│   └── dev/                # 开发期调试脚本（防风控实验等），不参与管线运行
├── Ech_youtube/             # YouTube 版（管线代码 + runs + LexFridman-博客笔记）
├── scripts/                 # 通用工具：check_env.py（自检）+ install.py/setup.*（一键装）
├── docs/                    # DEPLOY.md（部署与网络·必读）+ API_SETUP.md + 架构流程图 svg
├── .github/workflows/       # CI 冒烟（装依赖 + 自检）
├── research/                # 开源项目调研
└── 调研报告-*.md / 方案-*.html # 通用文档
```

| 平台 | 音频/视频获取 | 状态 |
|------|--------------|------|
| Bilibili（[Ech_bilibili/](Ech_bilibili/)） | playurl API 音频直取（完整浏览器头防 412）+ wbi 签名列表拉取 | ✅ 已实现并全量跑通（阿卡迪萨 447/447） |
| YouTube（[Ech_youtube/](Ech_youtube/)） | yt-dlp（无 B 站式风控）+ **字幕优先**（`subs_to_transcript.py`） | ✅ 已实现并全量跑通（Lex Fridman 447/447） |

> B 站适配是本项目最难啃的部分（匿名音频直取、风控对抗、wbi 签名），这些经验沉淀在 `Ech_bilibili/` 中；YouTube 版只需替换获取层，ASR/polish/笔记层全部复用。

## ⚠️ 部署与网络（必读——动服务器之前先看这一节）

**批量任务不在本机跑，而是「本机 + 服务器」分工。** 下面四条是实际踩坑得到的结论，
不读大概率会浪费时间——完整版见 **[docs/DEPLOY.md](docs/DEPLOY.md)**。

### ① 服务器上 YouTube 很可能够不着，要用反向隧道「借」本机的梯子

国内的校园网 / 实验室服务器上，`curl https://www.youtube.com` 会**直接超时**（不是 403，
是国际出口被限制；同机器 `pypi.org` 却正常）。**"服务器能上网" ≠ "服务器能上 YouTube"，这是两件事。**

解法是 **SSH 反向隧道**——本机→服务器方向本来就是通的，那就反着开一个端口：

```bash
# 本机执行（保持窗口开着）
ssh -N -R 17890:127.0.0.1:12000 <user>@<server>
#          │     └ 本机代理端口（你梯子的端口）
#          └ 在服务器上开的端口

# 服务器侧
export ECHONOTES_YT_PROXY=http://127.0.0.1:17890

# 验证（服务器上跑，期望 HTTP/2 200）
curl -sI --max-time 15 -x http://127.0.0.1:17890 https://www.youtube.com | head -1
```

**代价必须知道**：本机不在线 / 梯子关掉 → 服务器立刻失去外网。实测隧道断过一次，
直接产生 **99 条"字幕不可得"失败**。所以**跑批期间别关本机**。
有海外 VPS 的走直连即可：`export YT_PROXY=direct`（见 [Ech_youtube/SERVER.md](Ech_youtube/SERVER.md)）。

> 两个特征可用来判断隧道是否真的通了：返回 **`501 Unsupported method ('CONNECT')`**
> 说明请求打到了某个 Python `http.server` 哑服务（端口被占），不是真代理；
> 新隧道起不来多半是 **旧隧道进程没被杀死**（Windows 下结束作业杀不掉 ssh 子进程，要按 PID 清）。

### ② 字幕优先：能不下音频就不下

有官方字幕时走 `subs_to_transcript.py` 拉 VTT → 造出与 whisper **同构的 `transcript.json`**，
下游"说话人标注 → 翻译 → 渲染"全部复用。音频要 100MB 级/期（全量 ~50GB 上传），字幕只有 KB 级——
实测 447 期里**只有 4 期**因确实无英文字幕才回退 ASR。

### ③ LLM 额度：订阅看次数、token 包看 token、按量付费看钱

本项目负载"双高"：单期 ≈ **95 次调用 + 14 万 token**，全量 ≈ **4.2 万次 + 6300 万 token**。

| 计费类型 | 卡的维度 | 实测撞墙样子 |
|---|---|---|
| 包月订阅（Coding Plan） | **调用次数**（按时间窗） | `429` + `1308 已达到 5 小时的使用上限`，8 工人**几分钟**打光 |
| Token 包 | **token 总量** | `Your token-plan 1-week quota has been exhausted`，两天烧穿整周 |
| 按量付费 | **钱** | 447 期约 $1~2 |
| 免费档 | 次数/天 + 每分钟 | 日额度 250~500 次，**远远不够** |

对策已在管线里：**多 Key 轮换** + **配额类错误快速失败**（不做无意义重试，否则空烧 300s×5 次）+ 分级降级链。

### ④ 夸克网盘：中文**目录名**会导致 500（中文文件名没事）

用本机 OpenList 镜像产物到夸克时，`/quark/播客笔记` 这种**中文目录**会 `mkdir` 返回 200
但 `list` 返回 **500 object not found**（`refresh=true` 也无效）；纯 ASCII 路径嵌套两层正常。
根因是 **OpenList 的夸克驱动无法解析含中文的目录路径**——注意**中文文件名完全正常**。
修法：云端目录名一律 ASCII + 中文集合名做映射（`阿卡迪萨 → Akadisa`）。
另两个坑：**开机自启 VBS 不能有中文注释**（注释会吃掉换行导致整脚本失效）、
**`pythonw` 下 `sys.stdout is None`**（包装 stdout 前必须判空）。详见 [docs/DEPLOY.md](docs/DEPLOY.md)。

**实测规模参考**：Lex Fridman 447/447 + 阿卡迪萨 447/447，约 2 天跑完（8 工人并行 + 断点续跑），
产物 LexFridman 320MB / 阿卡迪萨 13MB。


## 环境准备（4 步）

### 0. 获取代码

**请用 HTTPS 地址，不要用 SSH 地址。** SSH 形态的 `git@github.com:...` 对**没配 SSH key** 的人会报

```
git@github.com: Permission denied (publickey).
fatal: Could not read from remote repository.
Please make sure you have the correct access rights and the repository exists.
```

——这句 **`correct access rights`** 看着非常像"仓库是私有的 / 你没权限"，其实只是**没配 key**，
和仓库可见性无关（本仓库是 public）。

```bash
# 推荐：浅克隆，快，且不需要任何 key（注意是 https://，不是 git@github.com:）
git clone --depth 1 https://github.com/WZAwza050801/Ech_bilibili.git
```

不想用 git 就直接下载压缩包：

```
https://github.com/WZAwza050801/Ech_bilibili/archive/refs/heads/main.zip
```

国内网络访问 GitHub 不稳定时（`Failed to connect to github.com port 443` / `Recv failure` /
`LibreSSL SSL_connect: ... unexpected eof`），套一层镜像加速前缀：

```bash
curl -L -o Ech_bilibili.zip \
  https://ghfast.top/https://github.com/WZAwza050801/Ech_bilibili/archive/refs/heads/main.zip
# gh-proxy.com / ghproxy.net 是同形前缀，可轮换使用
```

> **下不动基本不是体积问题**：仓库已跟踪文件总计约 **7 MB**，最大单文件 675 KB，**未使用 Git LFS**
> （所以不存在"克隆下来只有 LFS 指针、没有真文件"的情况）。`models/`、`runs/`、`audio.*` 等
> 大文件与中间产物都不进仓库，克隆后按下面第 2 步装依赖即可。

### 1. 系统要求

| 项目 | 版本要求 | 用途 | 缺失后果 |
|---|---|---|---|
| Python | >= 3.10 | 全部脚本 | 无法运行 |
| ffmpeg | 任意近期版本 | 音频直取后的转码与切片 | ASR 与抽帧直接失败 |

### 2. 安装依赖

懒得手动敲？一条命令把「装 ffmpeg + 建环境 + 装依赖 + 自检」一次做完：

```bash
python scripts/install.py                    # 全平台通用
python scripts/install.py --asr              # 额外装本地语音转写
python scripts/install.py --skip-ffmpeg      # 没权限动系统包管理器时

bash scripts/setup.sh                        # Linux / macOS（等价封装）
.\scripts\setup.ps1                          # Windows PowerShell（等价封装）
```

想手动来：

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows:     .venv\Scripts\activate

pip install -r requirements.txt          # 核心依赖（= 两个平台各自 requirements 之和）
pip install -r requirements-asr.txt      # 可选：本地语音转写（建议独立虚拟环境）
```

> 依赖刻意做薄：取流/请求主体只用标准库；`faster-whisper` 会拖入 ctranslate2 等重依赖，
> 因此单独放 `requirements-asr.txt`，装到独立 venv 后用 `ECHONOTES_ASR_PYTHON` 指过去，
> 避免与主线环境互相污染。`Ech_bilibili/requirements.txt` 与 `Ech_youtube/requirements.txt`
> 也各自列全了本平台依赖，想一个环境装齐直接用它们即可。

### 3. 自检（**跑管线前先跑它**）

```bash
python scripts/check_env.py                  # 全量检查
python scripts/check_env.py -p youtube       # 只查某个平台
python scripts/check_env.py --ci             # 只校验 Python 与 pip 依赖（CI 用）
python scripts/check_env.py -q               # 只打印结论
```

逐项打印 `[ OK ] / [WARN] / [FAIL]`，缺什么、去哪装、装完怎么验证一次说清；
有必需项缺失时退出码为 1。检查覆盖：Python 版本、pip 依赖、ffmpeg（含 `FFMPEG` 变量指向是否有效）、
磁盘剩余空间、平台目录可写性、whisper 模型、API 密钥、B 站接口连通、deno、YouTube 代理连通性。

**管线自己也会预检**：`pipeline1.py` / `yt_pipeline.py` / `yt_blog.py` 启动前会先检查缺什么，
缺依赖直接给出人话提示并以 **退出码 2** 结束——不会跑到一半才甩一条 traceback。

### 密钥

复制 `.env.example` 为 `.env` 后填写（`.env` 已被 `.gitignore` 拦截，永不入库）。
每个 Key 用在哪、为什么选这个模型、去哪申请，见 [docs/API_SETUP.md](docs/API_SETUP.md)。
Ech_bilibili 的必需 Key：**无（可不配 Key 跑通）**。

### 常见故障速查

| 症状 | 原因 | 解决 |
|---|---|---|
| `TypeError: expected str, bytes or os.PathLike object, not NoneType`（在 `ffmpeg_wav` 里） | `shutil.which("ffmpeg")` 返回 `None` 被直接传给 `subprocess` | 没装 ffmpeg 或没进 PATH。`python scripts/install.py` 或 `winget install Gyan.FFmpeg` 后重开终端；也可设 `FFMPEG=<完整路径>`。**现已根治：启动预检会提前给出人话提示** |
| `ModuleNotFoundError: No module named 'faster_whisper' / 'yt_dlp'` | 依赖没装，或装到了别的解释器 | `python scripts/install.py`；注意「用哪个解释器跑管线就往哪个装」，`check_env.py` 会打印当前解释器路径 |
| B 站返回 412 / -352 风控 | 缺少完整浏览器请求头或 wbi 签名 | 用 Ech_bilibili/ 内的防风控实现，勿自行简化请求头 |
| ffmpeg 找不到 | 未加入 PATH | `ffmpeg -version` 验证；Windows 用 winget 装完重开终端 |
| LLM 调用失败 / 401 / 超时 | Key 不对，或网络要走代理 | 检查 `DEEPSEEK_API_KEY`；国内默认代理 `127.0.0.1:12000`，海外服务器设 `YT_PROXY=direct` |
| **服务器上 YouTube 超时**（`curl: (28) Connection timed out`） | **国际出口被限制，不是配置问题** | 国内服务器必须走 **SSH 反向隧道**借本机梯子，见[docs/DEPLOY.md](docs/DEPLOY.md)；海外 VPS 设 `YT_PROXY=direct` |
| **隧道"通了"但请求 501** | 返回 `501 Unsupported method ('CONNECT')` | 请求打到了某个 Python `http.server` 哑服务，**端口被占**；清掉旧隧道进程（Windows 下按 PID 杀，结束作业杀不掉 ssh 子进程） |
| **批量成片"字幕不可得"** | 隧道中途断了（本机休眠/梯子掉线） | 恢复隧道后重跑即可（断点续跑，已完成的会跳过）；跑批期间别关本机 |
| **夸克网盘 `list` 返回 500** | 云端**目录名含中文**（OpenList 夸克驱动解析不了） | 目录名改 ASCII + 集合名做映射；**中文文件名不受影响**。见[docs/DEPLOY.md](docs/DEPLOY.md) |
| YouTube 报 n-challenge / 403 | 缺 JS runtime | 下载 deno 放 `Ech_youtube/bin/`（管线自动加 PATH），或配 `YT_PROXY` 代理 |
| ASR 很慢 / 转写中断 | 本地 small/int8 模型在 CPU 上跑 | 复用已有 `transcript.json`（管线支持断点续跑），或改用独立 venv 装 ASR 依赖 |
| 换了盘符 / 换了机器跑不动 | 以为路径写死了 | 其实全部走环境变量覆盖，见[环境变量参考](#环境变量参考)；先跑 `python scripts/check_env.py` |
| **`git clone` 报 `Permission denied (publickey)`** | 用了 **SSH 地址**（`git@github.com:...`）但没配 SSH key；**不是仓库私有** | 换 HTTPS：`git clone https://github.com/WZAwza050801/Ech_bilibili.git`，或直接下 [main.zip](https://github.com/WZAwza050801/Ech_bilibili/archive/refs/heads/main.zip) |
| **连不上 GitHub / 下载超时**（`Failed to connect ... port 443`） | 本地网络到 GitHub 不通，与仓库无关（仓库仅约 7 MB，未用 LFS） | 套镜像前缀：`https://ghfast.top/https://github.com/WZAwza050801/Ech_bilibili/archive/refs/heads/main.zip` |
| **卡片墙里点某个笔记 404** | 旧版产物文件名含 `#`（URL 锚点分隔符会把路径截断） | 已于 `b50574f` 修复（`safe_name()` 连带清洗 `#`/`%`）；历史文件已重命名 |

### 跑起来

```bash
python Ech_bilibili/pipeline1.py <B站视频链接>
```

## 三类内容管线（三仓库）

| 管线 | 输入形态 | 输出 | 仓库 |
|------|---------|------|------|
| 一 · 口播/观点类 | 播客、观点、推荐视频（纯音频） | 读书笔记 + 整理版逐字稿 | ✅ 本仓库（B站 + YouTube 双平台） |
| 二 · 课程类 | 数学/学术/技术课程 | LaTeX 可阅读讲义（tex + pdf） | ✅ [Ech_lecture](https://github.com/WZAwza050801/Ech_lecture) |
| 三 · 实操教程类 | PS/绘画/剪辑/开发教程 | 作品集（可运行工程 + mp4）+ 实验报告 | ✅ [Ech_practice](https://github.com/WZAwza050801/Ech_practice) |

## 全套流程图（合并-分叉架构 v2）

两条产物管线共享同一个前处理合并段（只跑一次），分叉产出**作品集**与 **LaTeX 讲义**，
统一归档到 `D:\B站课程Agent\BV<号>-<课名>\` 并自动清扫中间产物。

![架构总览](docs/architecture.svg)

| 图 | 位置 | 内容 |
|---|---|---|
| 架构总览 | 本仓库 [docs/architecture.svg](docs/architecture.svg) | 合并段 → 分叉双管线 → 统一归档 → 自动清扫 |
| 合并段内部 | 本仓库 [docs/flow-merged.svg](docs/flow-merged.svg) | 音视频直取 → ASR → 抽帧 → 视觉理解：每步的脚本/API/输入输出 |
| 管线三内部 | [Ech_practice/docs](https://github.com/WZAwza050801/Ech_practice/tree/main/docs) | 答案包 Quark 获取链 + 盲写→对账→校准→验证→渲染，全部脚本清单 |
| 管线二内部 | [Ech_lecture/docs](https://github.com/WZAwza050801/Ech_lecture/tree/main/docs) | 窗口 map → 写作 → 公式复查 → XeLaTeX：模型端点与配额、退出码语义 |
| 归档清扫内部 | 本仓库 [docs/flow-archive.svg](docs/flow-archive.svg) | organize.py 五步 + 校验规则 + 删除安全机制（三坑）+ GitHub 推送 |

> 历史分支（`feat/course-latex-pipeline` / `feature/pipeline3-practice`）保留作迁移前存档，
> 后续开发请到对应独立仓库。

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

- Python 3.10+，`faster-whisper`（优先加载 `models/faster-whisper-small`，目录不存在时自动退回 HF 模型名 `small` 下载）
- `ffmpeg` 在 PATH 中（Windows：`winget install Gyan.FFmpeg`，装完重开终端）；没装到 PATH 可用 `FFMPEG` 环境变量指向 ffmpeg.exe
- DeepSeek API Key：优先环境变量 `DEEPSEEK_API_KEY`，回退读本机密码书（仓库不含任何密钥）

### 产物归档命名规范

新增博主 / 新增视频一律照此落盘，不散落堆放：

```
Ech_bilibili/
├── 江左道卡卡-读书笔记/          # 外层：<创作者>-<笔记类型>
│   ├── 01-<标题>.html           # 内层：{NN}-{标题}.html（两位序号，从 01 起，不回收）
│   ├── index.html               # 卡片墙
│   ├── failed.json              # 失败清单
│   └── batch_log.txt            # 日志
└── runs/<视频ID>/               # 中间产物（B站用 BV 号，YouTube 用 11 位 vid）
    ├── audio.wav / transcript.json / polished.json
    └── 笔记.html                # 转写产物固定名（访谈类为 博客笔记.html）
```

标题处理规则（`safe_name()`）：Windows 非法字符 `\ / : * ? " < > |` 与空白替换为 `_`，
**另外 `#` 和 `%` 也必须替换** —— `#` 在 URL 里是锚点分隔符，会在 `#` 处把链接截断
（例：`样张-扎克伯格#267.html` 的卡片墙链接必 404），`%` 会被当成百分号转义。最后截断 60 字。

命名逻辑固化在 `batch_run.py`（B站）与 `yt_blog_batch.py`（YouTube）的 `safe_name()`，两处规则必须保持一致。

## 工程化设计（产品视角）

这一节回答一个面试官会问的问题：**"这东西交到别人手里能不能跑起来？"**

| 关注点 | 做法 |
|---|---|
| **不把环境问题甩给用户** | 三层防线：`scripts/install.py`（代装 ffmpeg/依赖）→ `scripts/check_env.py`（体检 + 修复命令）→ 管线内 `preflight()`（启动即拦截，exit 2，不甩 traceback） |
| **依赖声明明确** | 每平台独立 `requirements.txt` + 根 `requirements.txt` 聚合；重型 ASR 依赖独立 `requirements-asr.txt`；系统级二进制（ffmpeg/deno）注明安装命令并由安装脚本代装 |
| **失败信息可行动** | 所有报错都带「为什么 + 怎么修 + 可复制命令」，而不是裸异常栈 |
| **返回码语义化** | 环境问题 exit 2（管线）/ exit 1（自检），业务失败非 0，成功 0——便于 CI 与批量脚本判断 |
| **CI 冒烟** | `.github/workflows/ci.yml` 装依赖 → `check_env.py --ci` → `compileall` 导入冒烟 |
| **可复现** | 断点续跑 + 产物完整性校验 + 回收站机制，重跑一条命令即可 |
| **可移植** | 零硬编码语义：路径全部走环境变量覆盖，默认值按脚本位置推导 |
| **密钥安全** | 只从环境变量 / 本机密码书读，永不入库；`.gitignore` 显式排除 `.env`、密码书、cookie、sqlite |
| **幂等** | 缓存命中即跳过，且缓存也要过完整性校验（防假产物） |

## 环境变量参考

**所有变量都是可选的**，默认值自动适配脚本所在位置；换盘 / 换机器 / 上服务器都不用改代码。
命名上**同时接受 `ECHONOTES_*`（文档主推，与仓库名一致）与 `ECH_*`（历史别名）**，前者优先。

| 变量 | 默认 | 说明 |
|------|------|------|
| `ECHONOTES_ROOT` / `ECH_ROOT` | 仓库根 | 多平台根目录 |
| `ECHONOTES_BILI_DIR` / `ECH_BILI_DIR` | `$ROOT/Ech_bilibili` | B 站平台目录（脚本自包含） |
| `ECHONOTES_YT_DIR` / `ECH_YT_DIR` | `$ROOT/Ech_youtube` | YouTube 平台目录 |
| `ECHONOTES_ASR_MODEL` / `ECH_MODEL_DIR` | `Ech_bilibili/models/faster-whisper-small` | whisper 模型目录（两平台共享，不重复下载） |
| `ECH_MODEL` | 上述目录，否则 HF 模型名 `small` | 模型目录或 HF 模型名（缺目录时触发下载） |
| `ECHONOTES_ASR_PYTHON` / `ECH_PY` | 已知 venv，否则当前解释器 | 转写/polish 子进程使用的 python（独立 venv 场景） |
| `FFMPEG` | PATH 中的 `ffmpeg` | 指向 `ffmpeg` 可执行文件完整路径 |
| `DEEPSEEK_API_KEY` | 回退本机密码书 | LLM key（申请与配额见 `docs/API_SETUP.md`） |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | LLM 端点 |
| `ECHONOTES_SECRETS_FILE` / `ECH_SECRETS` | 本机密码书路径 | 密钥回退文件 |
| `ECHONOTES_YT_PROXY` / `YT_PROXY` | `http://127.0.0.1:12000` | YouTube 代理。**本机**填你梯子的端口；**国内服务器**填反向隧道端口（如 `http://127.0.0.1:17890`，见[docs/DEPLOY.md](docs/DEPLOY.md)）；**海外服务器**设 `direct` 直连。LLM 域名已在代码里进 `NO_PROXY`，不受此变量影响 |

## 管线二：课程视频 → LaTeX 讲义 ✅

> 独立仓库：[Ech_lecture](https://github.com/WZAwza050801/Ech_lecture)（本节为摘要）。

一条命令一个分P：`pipeline2.py run <B站链接> --page N` → **音视频直取 → Whisper ASR → 抽帧 → Qwen3-VL 视觉 map → 规划/写作（token plan 配额）→ 公式原帧复查 → XeLaTeX 两遍编译 → lecture.pdf**。

已验收课程：李群李代数（P1）、机器人学（P2）、Godot 游戏特效 8 个实操P（P02/P04/P05/P07-P11，单P 15~120 分钟，产物 1.5~8.9MB PDF）。内部细节见 [Ech_lecture 管线二流程图](https://github.com/WZAwza050801/Ech_lecture/blob/main/docs/flow-pipeline2.svg)。

## 管线三：实操教程 → 复刻作品集 ✅

> 独立仓库：[Ech_practice](https://github.com/WZAwza050801/Ech_practice)（本节为摘要）。

**闭卷盲写 → 与讲师标准答案对账 → 只校准关键参数（代码不抄）** 三段式：
产出可运行工程 + 效果预览 mp4。已验收：《自制简易计算器》（A级复刻）与
《Godot 游戏特效》全 12 分P（10 个特效场景 + 10 段 mp4，冒烟测试 10/10）。
内部细节见 [Ech_practice 管线三流程图](https://github.com/WZAwza050801/Ech_practice/blob/main/docs/flow-pipeline3.svg)。

## 路线图

- [x] 管线一端到端全自动（一条命令出笔记）
- [x] 批量模式：UP 主全部视频 → 笔记卡文件夹 + 卡片墙索引
- [x] 114 个视频批量实测（含风控对抗、假产物防御、OOM 修复全流程）
- [x] YouTube 平台适配（Ech_youtube/，Lex Fridman **447/447** 全量收官）
- [x] 字幕优先策略（`subs_to_transcript.py`：有官方字幕免 ASR，伪造与 whisper 同构的 `transcript.json`）
- [x] 服务器批量：多工人并行 + 断点续跑 + 密钥轮换（Lex 447/447 + 阿卡迪萨 447/447，约 2 天）
- [x] 网络攻坚：SSH 反向隧道让国内服务器"借"本机梯子访问 YouTube（见 [docs/DEPLOY.md](docs/DEPLOY.md)）
- [x] 配额感知：区分"订阅看次数 / token 包看 token / 按量付费看钱"，配额类错误快速失败不空烧
- [x] 产物镜像到网盘（OpenList + 夸克），并定位「中文目录名 500」根因（改用 ASCII 目录 + 名称映射）
- [x] 管线二：课程视频 → LaTeX 讲义（多模态 map + 公式原帧复查 + XeLaTeX）
- [x] 管线三：实操教程 → 作品集（盲写/对账/校准三段式 + Movie Maker 渲染）
- [x] 合并-分叉架构：共享前处理 + 统一归档 + 自动清扫
- [x] 三仓库拆分：Ech_bilibili（读书笔记）/ Ech_lecture（LaTeX 讲义）/ Ech_practice（复刻作品集）
- [x] **工程化：一键安装（scripts/install.py）+ 环境自检（check_env.py）+ 管线启动预检 + 依赖声明 + 零硬编码路径 + CI 冒烟**
- [x] **部署文档：docs/DEPLOY.md（部署与网络·必读：反向隧道 / 字幕优先 / 配额模型 / 网盘镜像坑）**
- [ ] 统一入口：一条命令跑完整门课（合并段 → 双分叉 → 归档清扫全自动串联）
- [ ] 隧道自动化：把反向隧道做成托管服务（当前需本机手动保持，断了批量会成片失败）
- [ ] 补跑 Lex 早期缺口的 54 期（官方播客页 501 期 vs 现有队列 447 期）
- [ ] 环境变量命名归一（`ECHONOTES_*` 为唯一主推，下线 `ECH_*` 别名）

## API 配置

本仓库用到哪些 Key、为什么选这些模型、在哪申请、怎么自检——见 [docs/API_SETUP.md](docs/API_SETUP.md)。密钥永不入库。