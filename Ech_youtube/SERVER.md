# 服务器部署手册（Linux VPS）

> 目标：把 Lex Fridman 447 期跑批从本机搬到海外 VPS（直连 YouTube，无风控）。

## 1. 机型建议

| 路线 | 配置 | 速度 | 参考价 |
|------|------|------|--------|
| CPU（推荐起步） | 8 核 16G | 单期(3h 节目)约 1-1.5h | $15-30/月 |
| CPU 加强 | 16 核 32G | 约 40min/期，或 2 并发 | $40-60/月 |
| GPU 冲刺 | 单卡 T4/4090 按小时租 | 10-20min/期 | $0.5-2/时，跑完就退 |

注意：whisper small/int8 CPU 推理吃内存带宽；分段转写单段峰值约 350MB，16G 足够。

## 2. 部署步骤

```bash
# 依赖
sudo apt update && sudo apt install -y ffmpeg python3-venv
curl -fsSL https://deno.com/install.sh | sh   # deno 进 PATH (yt-dlp 解 n-challenge 必需)

# 代码
git clone https://github.com/WZAwza050801/Ech_bilibili.git
cd Ech_bilibili/Ech_youtube
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# whisper 模型 (两种方式二选一)
#   A. 从本机拷贝: scp -r work/pipeline1/models/faster-whisper-small 服务器:Ech_bilibili/work/pipeline1/models/
#   B. 环境变量指向 HF 缓存目录(首次运行自动下载 small 模型)

# 配置 (海外机直连 YouTube, 无需代理)
export ECH_ROOT=$HOME/Ech_bilibili
export YT_PROXY=direct
export DEEPSEEK_API_KEY=sk-xxxxxxxx        # LLM 凭据走环境变量, 不依赖密码书

# 试跑单期
python yt_blog.py HUkBz-cdB-k --guest "Terence Tao"

# 全量跑批 (tmux 挂后台)
tmux new -s lex
python yt_blog_batch.py
# Ctrl+B D 脱离; tmux attach -t lex 回来
```

## 3. 配置项一览（ech_config.py）

| 环境变量 | 默认值(本机) | 说明 |
|----------|--------------|------|
| `ECH_ROOT` | `D:\视频观看agent编写` | 项目根目录 |
| `ECH_YT_DIR` | `$ECH_ROOT/Ech_youtube` | YouTube 管线目录 |
| `ECH_MODEL_DIR` | `work/pipeline1/models/faster-whisper-small` | whisper 模型 |
| `YT_PROXY` | `http://127.0.0.1:12000` | `direct`=直连(海外机) |
| `DEEPSEEK_API_KEY` | 回退读 `ECH_SECRETS` 密码书 | LLM 凭据 |
| `ECH_SECRETS` | `D:\密码书\private\...json` | 密码书路径(仅本机) |

## 4. 与本机的产物同步

服务器跑完的笔记在 `Ech_youtube/LexFridman-博客笔记/`，定时回拉即可：

```bash
# 本机 Windows (计划任务/手动)
scp -r user@vps:Ech_bilibili/Ech_youtube/LexFridman-博客笔记 D:\视频观看agent编写\Ech_youtube\
```

## 5. 断点与安全

- 每期独立断点：meta/audio/chunks/speakers/translation 五级缓存，中断重跑不重复计算
- 失败自动跳过并记 `failed.json`；bot-check 自动冷却 30 分钟
- 跑批脚本崩溃直接重启即可（卡片存在即跳过），也可用 systemd/循环包装自动拉起
