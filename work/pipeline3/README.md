# EchoNotes 管线三

把 B 站实操教程转换为：

1. 可检索的完整课程讲义；
2. 带真实执行记录的实验报告；
3. 在隔离环境中生成并验证的复刻作品。

## 当前能力

- B 站 DASH 音视频获取；
- `faster-whisper` 本地转写；
- Gemini Files API + 完整视频理解；
- 场景变化与均匀间隔融合抽帧；
- A/B/C 可执行性分级与结构化步骤校验；
- WSL `bubblewrap` 无网络隔离执行；
- Markdown 与响应式 HTML 报告。

## 安装

```powershell
cd work\pipeline3
python -m pip install -e .
```

需要系统已安装 `ffmpeg`、`ffprobe`、WSL、`bubblewrap`。ASR 依赖可通过
`python -m pip install -e ".[asr]"` 安装。

## 运行

```powershell
python -m echonotes_practice BV1fy4y1K7Mi `
  --run-dir "runs\开发实操-自制简易计算器-2026-09-18" `
  --secrets "D:\密码书\private\private-ai-api-secrets.json" `
  --asr-model "D:\视频观看agent编写\work\pipeline1\models\faster-whisper-small"
```

也可设置 `GEMINI_API_KEY`，省略 `--secrets`。`--polish` 会额外消耗模型请求，
仅在 ASR 可读性不足时使用。

## 产物

```text
runs/<内容-标题-日期>/
├── source/               # 原始音视频、ASR、元数据
├── overview-frames/      # 场景检测 + 均匀采样
├── evidence-frames/      # 操作步骤证据帧
├── artifact/             # 复刻作品
├── analysis.json         # 结构化教程分析
├── execution.json        # 每步实际执行与验证记录
└── outputs/
    ├── 课程讲义.md
    ├── 实验报告.md
    └── 讲义与实验报告.html
```

`runs/` 默认不进入 Git。

## 安全边界

- 视频和模型响应均视为不可信输入。
- 文件只能写入当次 `artifact/`，禁止绝对路径、目录穿越和 NTFS ADS。
- 命令使用参数数组，不经过 shell 展开。
- 默认命令白名单为 `python3`、`python`、`node`、`ffmpeg`。
- 沙箱无网络，仅只读挂载 Linux 运行时，并限制 CPU、内存和进程数。
- 依赖安装在 v1 中默认阻止，后续应通过人工批准的锁文件预先暂存。
