<#
.SYNOPSIS
    采集本周微信群截图（ADB 自动截图 + 滚动）。

.EXAMPLE
    .\scripts\run_capture_week.ps1 -Week 2026-W24
    .\scripts\run_capture_week.ps1 -Week 2026-W24 -Groups main
    .\scripts\run_capture_week.ps1 -Week 2026-W24 -Backfill 2026-06-07 -Groups trigger
    .\scripts\run_capture_week.ps1 -Week 2026-W24 -Force

如果系统里 `python` 命令不存在，把下面的 python 换成 `py`。
#>
param(
    [Parameter(Mandatory = $true)][string]$Week,
    [string]$Groups,
    [string]$Backfill,
    [switch]$Force,
    [int]$MaxScreens
)

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$pyArgs = @("src/wechat_capture_bot.py", "--week", $Week)
if ($Groups) { $pyArgs += @("--groups", $Groups) }
if ($Backfill) { $pyArgs += @("--backfill", $Backfill) }
if ($Force) { $pyArgs += "--force" }
if ($MaxScreens) { $pyArgs += @("--max-screens", $MaxScreens) }

python @pyArgs
