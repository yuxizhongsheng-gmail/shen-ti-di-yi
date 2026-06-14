<#
.SYNOPSIS
    一次性跑完 采集 -> OCR -> 规则检测，输出本周候选高光。

.EXAMPLE
    .\scripts\run_week_pipeline.ps1 -Week 2026-W24
    .\scripts\run_week_pipeline.ps1 -Week 2026-W24 -SkipCapture          # 截图已采集好
    .\scripts\run_week_pipeline.ps1 -Week 2026-W24 -SkipCapture -SkipOcr # 只重跑规则检测

如果系统里 `python` 命令不存在，把下面的 python 换成 `py`。
#>
param(
    [Parameter(Mandatory = $true)][string]$Week,
    [string]$Groups,
    [string]$Backfill,
    [int]$MaxScreens,
    [switch]$ForceCapture,
    [switch]$ForceOcr,
    [switch]$SkipCapture,
    [switch]$SkipOcr,
    [switch]$SkipDetect
)

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$pyArgs = @("src/weekly_pipeline.py", "--week", $Week)
if ($Groups) { $pyArgs += @("--groups", $Groups) }
if ($Backfill) { $pyArgs += @("--backfill", $Backfill) }
if ($MaxScreens) { $pyArgs += @("--max-screens", $MaxScreens) }
if ($ForceCapture) { $pyArgs += "--force-capture" }
if ($ForceOcr) { $pyArgs += "--force-ocr" }
if ($SkipCapture) { $pyArgs += "--skip-capture" }
if ($SkipOcr) { $pyArgs += "--skip-ocr" }
if ($SkipDetect) { $pyArgs += "--skip-detect" }

python @pyArgs
