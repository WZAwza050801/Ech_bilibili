# 一键上手（Windows）：装 ffmpeg -> 建虚拟环境 -> 装依赖 -> 自检
# 真正逻辑在 scripts/install.py，跨平台同一份。
# 用法:
#   .\scripts\setup.ps1                # 全自动
#   .\scripts\setup.ps1 -Asr           # 额外装本地语音转写
#   .\scripts\setup.ps1 -NoVenv        # 装到当前解释器（已在 venv 里时用）
#   .\scripts\setup.ps1 -SkipFfmpeg    # 不动系统包管理器
param(
    [switch]$Asr,
    [switch]$NoVenv,
    [switch]$SkipFfmpeg
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

$py = $null
foreach ($cand in @("py", "python", "python3")) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) { $py = $cand; break }
}
if (-not $py) {
    Write-Host "[x] 没找到 Python。请先安装 3.10+：" -ForegroundColor Red
    Write-Host "    winget install Python.Python.3.12"
    exit 1
}

$installArgs = @("$here\install.py")
if ($Asr)        { $installArgs += "--asr" }
if ($NoVenv)     { $installArgs += "--no-venv" }
if ($SkipFfmpeg) { $installArgs += "--skip-ffmpeg" }

if ($py -eq "py") { & py -3 @installArgs } else { & $py @installArgs }
exit $LASTEXITCODE
