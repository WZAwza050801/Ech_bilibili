#!/usr/bin/env bash
# 一键上手（Linux / macOS）：装 ffmpeg -> 建虚拟环境 -> 装依赖 -> 自检
# 真正逻辑在 scripts/install.py，跨平台同一份。
# 用法:
#   bash scripts/setup.sh                # 全自动
#   bash scripts/setup.sh --asr          # 额外装本地语音转写
#   bash scripts/setup.sh --no-venv      # 装到当前解释器（已在 venv 里时用）
#   bash scripts/setup.sh --skip-ffmpeg  # 不动系统包管理器
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

py=""
for cand in "${PYTHON:-}" python3 python; do
    [ -n "$cand" ] || continue
    if command -v "$cand" >/dev/null 2>&1; then py="$cand"; break; fi
done
if [ -z "$py" ]; then
    echo "[x] 没找到 Python。请先安装 3.10+（Debian/Ubuntu: sudo apt install python3 python3-venv）" >&2
    exit 1
fi

exec "$py" "$here/install.py" "$@"
