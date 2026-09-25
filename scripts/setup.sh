#!/usr/bin/env bash
# 一键上手：建虚拟环境 -> 装依赖 -> 自检
# 用法: bash scripts/setup.sh      （加 --asr 额外装本地语音转写）
set -euo pipefail

PY=${PYTHON:-python3}
$PY -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

if [[ "${1:-}" == "--asr" ]]; then
  pip install -r requirements-asr.txt
fi

echo
echo "依赖装好了，开始自检（缺什么会直接告诉你怎么补）："
python scripts/check_env.py
