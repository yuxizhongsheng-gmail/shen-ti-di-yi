<#
.SYNOPSIS
    对本周 OCR 文本做规则化高响应事件检测（不调用大模型）。

.EXAMPLE
    .\scripts\run_detect_week.ps1 -Week 2026-W24

如果系统里 `python` 命令不存在，把下面的 python 换成 `py`。
#>
param(
    [Parameter(Mandatory = $true)][string]$Week
)

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

python src/event_detector.py --week $Week
