# 服务器部署手册

> 把 Lex Fridman / 任意 YouTube 播放列表搬到服务器上批量跑。
>
> **先读 [../docs/DEPLOY.md](../docs/DEPLOY.md)**——网络、配额、归档的坑都写在那里，
> 本文只讲"怎么装、怎么起"。

## 0. 先选路线：你的服务器能不能直连 YouTube？

| 路线 | 适用 | 代理设置 | 代价 |
|---|---|---|---|
| **A · 国内服务器 + SSH 反向隧道** | 实验室集群 / 国内云主机（**本项目实测走的就是这条**） | `ECHONOTES_YT_PROXY=http://127.0.0.1:17890` | 本机必须在线且梯子开着；本机掉线 = 批量成片失败 |
| **B · 海外 VPS 直连** | 有海外机器 | `YT_PROXY=direct` | 要花钱；但可完全无人值守 |

**判断方法（在服务器上跑）**：

```bash
curl -sI --max-time 10 https://www.youtube.com | head -1
# HTTP/2 200  → 路线 B，直连即可
# curl: (28) Connection timed out  → 路线 A，必须搭隧道
```

> ⚠️ 别用"服务器能不能 pip install"来判断——`pypi.org` 通 **不代表** YouTube 通，
> 实测国内某高校集群节点上两者结果正好相反。

---

## 路线 A：国内服务器 + 反向隧道（实测路线）

### A1. 装依赖

```bash
sudo apt update && sudo apt install -y ffmpeg python3-venv
# deno（yt-dlp 解 n-challenge 用）：下载后放 PATH 或 Ech_youtube/bin/
curl -fsSL https://deno.com/install.sh | sh
```

> `python3-venv` 很容易漏——Ubuntu 上不装它 `python3 -m venv` 会失败。

### A2. 传代码与模型

```bash
# 代码（也可以 git clone，视网络情况）
scp -r ./Ech_youtube <user>@<server>:~/workspace/

# whisper 模型 464MB：两个平台共享同一份，只传一次
scp -r ./Ech_bilibili/models/faster-whisper-small <user>@<server>:~/workspace/Ech_bilibili/models/

# venv
ssh <user>@<server>
cd ~/workspace/Ech_youtube && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### A3. 起隧道（**在本机执行，不是服务器**）

```bash
ssh -N -R 17890:127.0.0.1:12000 <user>@<server>
#          │     └ 本机梯子/代理端口（按你的实际情况改）
#          └ 在服务器上开的端口（挑一个没被占用的）
```

保持这个窗口开着。**跑批全程都不能关本机、不能关梯子。**

### A4. 服务器侧配代理并验证

```bash
export ECHONOTES_YT_PROXY=http://127.0.0.1:17890
# 也可以写进 ~/.bashrc 持久化

curl -sI --max-time 15 -x http://127.0.0.1:17890 https://www.youtube.com | head -1
# 必须看到 HTTP/2 200 才能往下走
```

### A5. 试跑单期，再放批量

```bash
python yt_blog.py <video_id> --host "Lex Fridman" --guest "<嘉宾名>"
# 确认产物正确后再放批量：

# 批量（后台挂住；断点续跑，已完成的会跳过）
nohup python yt_blog_batch.py > batch.log 2>&1 &
```

**先小并发验证机制，再放全量。** 实测 8 工人 + 密钥轮换是可用配置，但建议先 `WORKERS=2` 跑几期。

---

## 路线 B：海外 VPS 直连

### B1. 机型建议

| 配置 | 速度 | 参考价 |
|---|---|---|
| 8 核 16G | 单期(3h 节目)约 1-1.5h | $15-30/月 |
| 16 核 32G | 约 40min/期，或 2 并发 | $40-60/月 |
| 单卡 T4/4090（按小时租） | 10-20min/期 | $0.5-2/时，跑完就退 |

whisper small/int8 在 CPU 上吃内存带宽；分段转写单段峰值约 350MB，16G 够用。

### B2. 部署

```bash
sudo apt update && sudo apt install -y ffmpeg python3-venv
curl -fsSL https://deno.com/install.sh | sh

cd ~/Ech_youtube && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

export ECH_ROOT=$HOME
export YT_PROXY=direct                 # 关键：海外机直连，关掉代理
export DEEPSEEK_API_KEY=sk-xxxxxxxx    # 凭据走环境变量，不依赖本机密钥文件

python yt_blog.py <video_id> --guest "<嘉宾名>"     # 试跑
tmux new -s lex && python yt_blog_batch.py          # 全量（Ctrl+B D 脱离）
```

---

## 配置项一览（`ech_config.py`）

| 环境变量 | 默认值（本机） | 说明 |
|---|---|---|
| `ECHONOTES_ROOT` / `ECH_ROOT` | 仓库根 | 项目根目录 |
| `ECHONOTES_YT_DIR` / `ECH_YT_DIR` | `$ROOT/Ech_youtube` | YouTube 管线目录 |
| `ECHONOTES_BILI_DIR` / `ECH_BILI_DIR` | `$ROOT/Ech_bilibili` | Bilibili 目录（仅共享 whisper 模型时用到） |
| `ECHONOTES_ASR_MODEL` / `ECH_MODEL_DIR` | `Ech_bilibili/models/faster-whisper-small` | whisper 模型（两平台共享） |
| `ECHONOTES_YT_PROXY` / `YT_PROXY` | `http://127.0.0.1:12000` | **路线 A 填隧道端口**；**路线 B 填 `direct`** |
| `ECHONOTES_ASR_PYTHON` / `ECH_PY` | 已知 venv，否则当前解释器 | ASR 独立环境时的 python |
| `DEEPSEEK_API_KEY` | 回退本机密钥文件 | LLM 凭据 |
| `ECHONOTES_SECRETS_FILE` / `ECH_SECRETS` | 本机密钥文件路径 | 仅本机用 |

> 命名上**同时接受 `ECHONOTES_*`（主推）与 `ECH_*`（历史别名）**，前者优先。

---

## 产物同步回本机

```bash
scp -r <user>@<server>:~/workspace/笔记归档/. ./视频笔记/
```

归档结构：`<创作者>/` 下 `NN-标题.html` + `index.html`（卡片墙）+ `README.md` + `归档报告.md`
（归档报告里的"缺失"应为 0）。

---

## 断点与安全

- 每期独立断点：meta / audio / chunks / speakers / translation 多级缓存，中断重跑不重复计算
- 失败自动跳过并记 `failed.json`；bot-check 自动冷却
- **LLM 配额是最容易崩的一环**：多工人务必配**密钥轮换**，并区分"订阅看调用次数 / token 包看 token 总量 /
  按量付费看钱"——详见 [../docs/DEPLOY.md](../docs/DEPLOY.md) 第 3 节
- 跑批脚本崩溃直接重启即可（卡片存在即跳过）
