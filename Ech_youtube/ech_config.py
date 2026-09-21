# -*- coding: utf-8 -*-
"""ech_config.py — Ech 系列管线全局配置(跨平台)
所有路径/密钥均支持环境变量覆盖, Windows 默认值保证本机行为不变。
服务器部署: 设 ECH_ROOT / ECH_SECRETS(或直接 DEEPSEEK_API_KEY) / YT_PROXY=direct 即可。
"""
import json
import os
from pathlib import Path

# ---- 根目录 ----
ECH_ROOT = Path(os.environ.get("ECH_ROOT", r"D:\视频观看agent编写"))
ECH_YT_DIR = Path(os.environ.get("ECH_YT_DIR", str(ECH_ROOT / "Ech_youtube")))
ECH_BILI_WORK = Path(os.environ.get("ECH_BILI_WORK", str(ECH_ROOT / "work" / "pipeline1")))

# ---- whisper 模型(共享目录) ----
ECH_MODEL_DIR = Path(os.environ.get("ECH_MODEL_DIR", str(ECH_BILI_WORK / "models" / "faster-whisper-small")))

# ---- 网络代理 ----
# direct = 直连(海外服务器推荐); 其他值 = http 代理地址
ECH_PROXY = os.environ.get("YT_PROXY", "http://127.0.0.1:12000")

# 子进程(deno 解 n-challenge 等)不会读 yt-dlp 的 proxy 参数, 需要标准环境变量
if ECH_PROXY and ECH_PROXY != "direct":
    for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        os.environ.setdefault(_k, ECH_PROXY)
    os.environ["NO_PROXY"] = "api.deepseek.com,127.0.0.1,localhost"

def ydl_proxy():
    """yt-dlp 用的 proxy 参数; direct 返回 None"""
    return None if ECH_PROXY == "direct" else ECH_PROXY

# ---- LLM 凭据: 优先环境变量 DEEPSEEK_API_KEY, 回退密码书 ----
ECH_SECRETS = Path(os.environ.get("ECH_SECRETS", r"D:\密码书\private\private-ai-api-secrets.json"))

def llm_credentials():
    """返回 (api_key, base_url, model)。服务器上只需 export DEEPSEEK_API_KEY=sk-xxx"""
    env_key = os.environ.get("DEEPSEEK_API_KEY")
    if env_key:
        return env_key, os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"), "deepseek-chat"
    secrets = json.load(open(str(ECH_SECRETS), encoding="utf-8"))
    entry = next(e for e in secrets["entries"] if e.get("label") == "Environment DEEPSEEK_API_KEY")
    return entry["apiKey"], (entry.get("baseUrl") or "https://api.deepseek.com").rstrip("/"), "deepseek-chat"
