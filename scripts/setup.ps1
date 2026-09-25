# 一键上手：建虚拟环境 -> 装依赖 -> 自检
# 用法: .\scripts\setup.ps1        （加 -Asr 额外装本地语音转写）
param([switch]$Asr)

$ErrorActionPreference = "Stop"

python -m venv .venv
. .\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
if ($Asr) { pip install -r requirements-asr.txt }

Write-Host ""
Write-Host "依赖装好了，开始自检（缺什么会直接告诉你怎么补）："
python scripts/check_env.py
