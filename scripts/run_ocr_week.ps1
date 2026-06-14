<#
.SYNOPSIS
    对本周已采集的截图做本地 OCR。

.EXAMPLE
    .\scripts\run_ocr_week.ps1 -Week 2026-W24
    .\scripts\run_ocr_week.ps1 -Week 2026-W24 -Force   # 忽略缓存，全部重新识别

如果系统里 `python` 命令不存在，把下面的 python 换成 `py`。
#>
param(
    [Parameter(Mandatory = $true)][string]$Week,
    [switch]$Force
)

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$pyArgs = @("src/ocr_extract.py", "--week", $Week)
if ($Force) { $pyArgs += "--force" }

python @pyArgs
