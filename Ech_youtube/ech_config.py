# -*- coding: utf-8 -*-
"""ech_config.py — Ech 系列管线全局配置(跨平台)

所有路径/密钥均支持环境变量覆盖, Windows 默认值保证本机行为不变。

环境变量命名：同时接受 `ECHONOTES_*`（文档主推，与仓库名一致）与 `ECH_*`（历史别名），
前者优先。例：ECHONOTES_ASR_MODEL 与 ECH_MODEL_DIR 等价，设了哪个都认。

服务器部署: 设 ECHONOTES_ROOT / ECHONOTES_SECRETS_FILE(或直接 DEEPSEEK_API_KEY) / YT_PROXY=direct 即可。
"""
import json
import os
from pathlib import Path


def _env(*names, default=None):
    """按顺序取第一个非空环境变量；用于 ECHONOTES_* / ECH_* 双命名兼容"""
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return default


# ---- 根目录 ----
ECH_ROOT = Path(_env("ECHONOTES_ROOT", "ECH_ROOT", default=r"D:\视频观看agent编写"))
ECH_YT_DIR = Path(_env("ECHONOTES_YT_DIR", "ECH_YT_DIR", default=str(ECH_ROOT / "Ech_youtube")))
ECH_BILI_DIR = Path(_env("ECHONOTES_BILI_DIR", "ECH_BILI_DIR", default=str(ECH_ROOT / "Ech_bilibili")))

# ---- whisper 模型(共享目录) ----
ECH_MODEL_DIR = Path(_env("ECHONOTES_ASR_MODEL", "ECH_MODEL_DIR",
                          default=str(ECH_BILI_DIR / "models" / "faster-whisper-small")))

# ---- 语音转写用的 python(独立 venv 场景) ----
ASR_PYTHON = _env("ECHONOTES_ASR_PYTHON", "ECH_PY")

# ---- 网络代理 ----
# direct = 直连(海外服务器推荐); 其他值 = http 代理地址
ECH_PROXY = _env("ECHONOTES_YT_PROXY", "ECH_YT_PROXY", "YT_PROXY", default="http://127.0.0.1:12000")

# 子进程(deno 解 n-challenge 等)不会读 yt-dlp 的 proxy 参数, 需要标准环境变量
if ECH_PROXY and ECH_PROXY != "direct":
    for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        os.environ.setdefault(_k, ECH_PROXY)
    os.environ["NO_PROXY"] = "api.deepseek.com,127.0.0.1,localhost"

def ydl_proxy():
    """yt-dlp 用的 proxy 参数; direct 返回 None"""
    return None if ECH_PROXY == "direct" else ECH_PROXY

# ---- LLM 凭据: 优先环境变量 DEEPSEEK_API_KEY, 回退密码书 ----
ECH_SECRETS = Path(_env("ECHONOTES_SECRETS_FILE", "ECH_SECRETS",
                        default=r"D:\密码书\private\private-ai-api-secrets.json"))

def llm_credentials():
    """返回 (api_key, base_url, model)。服务器上只需 export DEEPSEEK_API_KEY=sk-xxx"""
    env_key = os.environ.get("DEEPSEEK_API_KEY")
    if env_key:
        return env_key, os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"), "deepseek-chat"
    secrets = json.load(open(str(ECH_SECRETS), encoding="utf-8"))
    entry = next(e for e in secrets["entries"] if e.get("label") == "Environment DEEPSEEK_API_KEY")
    return entry["apiKey"], (entry.get("baseUrl") or "https://api.deepseek.com").rstrip("/"), "deepseek-chat"
