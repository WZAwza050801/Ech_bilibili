# 管线二：课程视频 → LaTeX 讲义

输入 B 站单集、指定分 P，或本地视频，输出可回查证据的中文 LaTeX/PDF 讲义。
采用多模态模型直接读板书/PPT；当前不安装 Pix2Text。

## 运行

在仓库根目录运行（Python 3.11+，ffmpeg、ffprobe、XeLaTeX 在 PATH 中）：

```powershell
python -m pip install -r work/pipeline2/requirements.txt
python -m work.pipeline2.pipeline2 doctor

$env:ECHONOTES_SECRETS_FILE = '你的外部密钥JSON路径'
$env:ECHONOTES_VISION_MODEL = 'qwen/qwen3-vl-235b-a22b-instruct'
python -m work.pipeline2.pipeline2 run 'https://www.bilibili.com/video/BV.../?p=2'
```

密钥文件沿用管线一注册表格式：
`{"entries":[{"provider":"deepseek","label":"...","apiKey":"...","baseUrl":"...","models":["deepseek-chat"]},...]}`。
不要把真实密钥文件放进仓库。

也支持环境变量：

| 变量 | 用途 |
|---|---|
| `ECHONOTES_TEXT_PROVIDER` / `ECHONOTES_VISION_PROVIDER` | 默认 `deepseek` / `openrouter` |
| `ECHONOTES_TEXT_MODEL` / `ECHONOTES_VISION_MODEL` | 默认 `deepseek-chat` / `qwen/qwen3-vl-235b-a22b-instruct` |
| `ECHONOTES_TEXT_BASE_URL` / `ECHONOTES_VISION_BASE_URL` | chat/completions 之前的完整 API 根地址 |
| `ECHONOTES_TEXT_API_KEY` / `ECHONOTES_VISION_API_KEY` | 独立密钥，优先于密钥文件 |
| `ECHONOTES_TEXT_KEY_LABEL` / `ECHONOTES_VISION_KEY_LABEL` | 从注册表精确选择 label |
| `DEEPSEEK_API_KEY` / `OPENROUTER_API_KEY` | 未提供专用密钥和注册表时的兜底 |
| `BILIBILI_COOKIE` | 本地提供的完整 cookie 请求头 |
| `ECHONOTES_ASR_PYTHON` | 已安装 faster-whisper 的解释器 |
| `ECHONOTES_ASR_MODEL` | 本地模型路径或 `small` |
| `ECHONOTES_ASR_CPU_THREADS` / `ECHONOTES_ASR_BEAM_SIZE` | 默认 `2` / `3`，内存紧张时可设为 `1` / `1` |

无 cookie 环境变量时，只读取相邻管线一源码中的既有浏览器 cookie 字面量，不导入其有副作用的入口。
不会读取浏览器登录数据库，也不把运行时 cookie / 密钥 / CDN 签名 URL 存到产物。
接口若返回 412，需检查现有登录态/访问权限；不切回 yt-dlp。

复用已有 Whisper 环境时，主程序只需要 Pillow；用 `--asr-python` 和
`--asr-model` 指定现有解释器与 small 模型目录，无需再次下载模型。

```powershell
# 已有本地视频和时间戳转写：跳过下载与 ASR
python -m work.pipeline2.pipeline2 run 'course.mp4' --transcript 'transcript.json'

# 本地 Whisper 被其他任务占用时，可生成诚实标注为30秒粒度的云端 ASR
python -m work.pipeline2.cloud_asr 'audio.wav' 'cloud-transcript.json' `
  --secrets '外部密钥文件路径' --chunk-seconds 30
python -m work.pipeline2.pipeline2 run 'course.mp4' --transcript 'cloud-transcript.json'

# 只准备音画证据，不调用云模型
python -m work.pipeline2.pipeline2 run 'course.mp4' --prepare-only

# 慢速板书默认每30秒采样；密集书写可调为10秒，并扩大帧预算
python -m work.pipeline2.pipeline2 run 'BV...' --interval 10 --max-frames 720

# 可独立关闭格式整理、视觉公式复查或 PDF 编译
python -m work.pipeline2.pipeline2 run 'BV...' --no-polish --no-verify --no-compile
```

`BV...` 是待替换示例。链接必须是完整 `bilibili.com/video/BV...` 链接，
暂不处理 b23 短链接和整合集；`?p=N` 或 `--page N` 选择一集。
已有转写格式：`{"segments":[{"start":0,"end":3.2,"text":"..."}]}`，时间相对于视频起点。

## 实现与证据边界

1. **获取**：复用管线一的 playurl 直取方式与完整浏览器头；DASH 视频优先 AVC、
   最高 1080p，分别下载音视频后合并。失败下载使用 `.part` 临时文件。
2. **语音**：CPU small/int8，`vad_filter=True, condition_on_previous_text=False`。
   原始 JSON 单独保存。格式整理沿用禁改写、ID 对齐与热词双端应用思路，
   对明显字数漂移回退原文。课程热词表默认空，不套用口播领域词典。
3. **画面**：先检测场景，再融合均匀骨架与 max-min 场景点。场景采样采用 ffmpeg，
   算法为本项目实现，没有复制调研仓库源码。记录 requested_t、原始 PTS、
   归一化 actual_t。dHash 与像素差联合保守去重，每次出现仍保留证据 ID。
   不使用文字密度规则自动删除人像，以免把重要画面误判。
4. **map**：默认 10 分钟，超过 8 张候选帧再按时间细分。跨窗口讲话段会出现在相邻窗口，
   每个候选帧都进入一个窗口。模型产出连贯讲解与定义/定理/证明/推导/例题块，
   每块及公式都有来源；代码拒绝虚构证据 ID。
5. **reduce**：有界分组编排全部知识块，检查每个块恰好出现一次。
   整合层不能重写原公式；跨段符号多义会列为待核验。
6. **公式复查**：对提取公式再读其原始帧，记录 `match / mismatch / unclear`。
   无画面来源或主动关闭时为 `not_checked`。不自动“修成常见公式”。
7. **排版**：程序控制 ctex/AMS 模板，普通文字转义、数学命令白名单、
   XeLaTeX 禁 shell escape，编译两遍。未知数学命令显示原文及待排版提示；
   已允许但语法错误的公式仍会导致明确编译失败，保留日志。

缓存以输入、模型、prompt、参数与帧内容摘要为键；参数或证据变化时重跑相应步骤。
同一视频有运行锁；异常退出后清理锁，进程被强制结束留下的锁需确认旧进程已停后移除。
模型 JSON 编码失败或出现疑似 LaTeX 转义控制字符时，最多请求一次仅编码修复；
再次失败则停止，不静默接受损坏公式。
本地 ASR 默认限制 CTranslate2/MKL 并发，避免按 CPU 核心数放大内存；每 50 段写一次
`asr-output.partial.json` 检查点。该检查点仅用于故障诊断，完整成功后才进入正式缓存。

## 产物

### 一体化学习笔记（推荐阅读版）

在 `run` 已生成的 `lecture.json` 上，可以继续生成带学习目标和理解批注的单一 PDF：

```powershell
$env:ECHONOTES_PLANNER_MODEL = 'deepseek-v4-pro'
$env:ECHONOTES_WRITER_MODEL = 'deepseek-v4-pro'
python -m work.pipeline2.study '归档路径/lecture.json' `
  --output-root 'output/学习讲义' --secrets '外部密钥文件路径'
```

规划器和写作者默认通过 DeepSeek 直连；可分别配置
`ECHONOTES_PLANNER_PROVIDER / BASE_URL / KEY_LABEL / MODEL / MAX_TOKENS` 和
`ECHONOTES_WRITER_*`。视觉识别复用 `ECHONOTES_VISION_*`。
必须显式指定规划、写作模型，避免自动回落到清洗模型。外部密钥格式与主流程一致。

全课规划生成可检查的基础、深入、迁移目标及课程专属写作指导；按连续语义单元选一张代表图。
每单元包含整理后的讲解、LaTeX 笔记、标明来源的补充推导、理解批注与自测。

写作是四道工序，全部带缓存与一次编码修复：初稿（`study-unit.md`）→
出版级深化（`study-deepen.md`：补全跳步推导、加最小可算例子、深化批注；
source 证据 ID 逐条保留，代码会拒绝丢失课堂来源的扩写）→
逐单元数学审校（`study-review.md`，`quality.json` 记录修订理由）→
全书文风统一（`study-style.md`：只允许改写各单元批注，统一术语与口吻，findings 记入 quality）。
模型审校不是严格证明，疑点需回看原视频。

课程地图锁定后，规划模型另生成一张**课程概念地图**（`concept-map.md` +
`concept_map.py`）：8-20 个概念节点按学习单元分列，边标注依赖/推广/应用/对比等关系；
Python 负责全部排版布局，模型只决定概念与关系。地图页印在目录前，随 study.json 存档。

产出两种排版，内容同源：
- `学习讲义.pdf`（`book.tex`，出版编排）：连续行文为主，〔补充〕标题标记编辑推导，
  批注用绿色竖线段，思考题与疑点弱化为节末元素。
- `学习讲义-卡片版.pdf`（`lecture.tex`，卡片编排）：蓝/绿/紫/红 `tcolorbox` 色块版。
`study.json`、`learning-plan.json`、`writing-brief.md`、缓存与质量报告供复查和再次生成。
本命令复用已有音画证据，当前尚未接入 Gemini 原生整视频上传。设计依据见 `LEARNING_DESIGN.md`。

默认工作目录：`work/pipeline2/runs/<BV-P或本地内容ID>/`。

默认归档：`output/课程讲义/课程讲义-标题-日期-来源ID-内容摘要/`。
可以用 `--output-root` 更改归档根目录。摘要避免同日不同版本互相覆盖。

- `lecture.tex` / `lecture.pdf`：讲义、符号表、核验提醒、可点击的原帧附录。
- `lecture.json` / `blocks.json`：可再编辑的结构化讲义。
- `transcript.raw.json` / `transcript.json`：原始与整理版转写。
- `frames/` / `frames.json` / `alignment.json`：原帧、实际时间戳、音画对齐。
- `quality.json`：公式复查、符号冲突、疑点、未引用证据、编译与排版警告。
- `manifest.json`：归档文件 SHA-256 与源视频摘要；不归档原始视频和密钥。

## 验证

```powershell
python -m unittest discover -s work/pipeline2/tests -v

# 真 ffmpeg + 真 XeLaTeX，固定假模型；只测试控制流，不能作为识别效果评测
python -m work.pipeline2.tests.test_pipeline 'output/pipeline2-integration'
```

当前限制：

- **编译通过不等于数学正确**，同模型二次视觉核验也不是独立数学审稿。
- 抽帧间隔和预算会漏掉短暂板书；当前没有自动补帧闭环，需调密重跑。
- “所有生成知识块都保留”不是“原视频语义全覆盖”；未引用转写/帧清单辅助人工审查。
- 不自动补全没有证据的证明；模糊符号、音画矛盾必须保留疑点。
- API 可用性、地区与账户权限由所选服务决定；不自动充值或绕过限制。
- 云端 ASR 兜底默认使用 SiliconFlow `TeleAI/TeleSpeechASR`，时间戳仅精确到切片区间；
  产物中的 `timestamp_precision` 会保留这一限制，不能冒充逐句精确时间。
- 真实长课质量需用用户指定视频验收，合成样例只证明管线连通和接口契约。
