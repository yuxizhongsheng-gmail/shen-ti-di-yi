# IP 群高光 · 从截图到候选事件（一键运行）
#
# 用法：
#   .\scripts\build_candidate_events.ps1 -Week 2026-W24
#   .\scripts\build_candidate_events.ps1 -Week 2026-W24 -Force   # 忽略 OCR 缓存
#
# 前提：
#   把本周截图放进 inbox\adb_captures\<week>\main\  （文件名任意，推荐 0001.png）
#   （可选）触发源群截图放进 inbox\adb_captures\<week>\trigger\
#
# 输出：
#   runs\<week>\capture_manifest.json   截图清单
#   runs\<week>\ocr_cache.json          OCR 缓存
#   runs\<week>\ocr_text.md             OCR 可读文本
#   runs\<week>\event_scores.json       事件分数
#   runs\<week>\candidate_events.md     候选高光事件（交给 Claude/GPT 编辑）

param(
    [Parameter(Mandatory=$true)][string]$Week,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host ""
Write-Host "===== IP 群高光 Pipeline · $Week =====" -ForegroundColor Cyan

# ── Step 1: 建立截图清单 ──────────────────────────────────────────────
Write-Host ""
Write-Host "[1/3] 扫描截图目录 -> capture_manifest.json" -ForegroundColor Yellow
python src/build_manifest.py --week $Week
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ⚠️  build_manifest 失败，请检查上方错误。" -ForegroundColor Red
    exit 1
}

# ── Step 2: OCR 文字提取 ─────────────────────────────────────────────
Write-Host ""
Write-Host "[2/3] OCR 文字提取 -> ocr_text.md" -ForegroundColor Yellow
if ($Force) {
    python src/ocr_extract.py --week $Week --force
} else {
    python src/ocr_extract.py --week $Week
}
if ($LASTEXITCODE -eq 1) {
    Write-Host ""
    Write-Host "  ℹ️  OCR 引擎未就绪。请按提示填写手动模板后重新运行此脚本。" -ForegroundColor DarkYellow
    exit 1
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ⚠️  OCR 提取失败，请检查上方错误。" -ForegroundColor Red
    exit 1
}

# ── Step 3: 事件检测 & 评分 ──────────────────────────────────────────
Write-Host ""
Write-Host "[3/3] 事件检测 -> candidate_events.md" -ForegroundColor Yellow
python src/event_detector.py --week $Week
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ⚠️  event_detector 失败，请检查上方错误。" -ForegroundColor Red
    exit 1
}

# ── 完成 ──────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "===== ✅ 全部完成 =====" -ForegroundColor Green
Write-Host "  候选事件：runs\$Week\candidate_events.md"
Write-Host "  下一步：把 candidate_events.md 交给 Claude/GPT，执行 prompts/03-score-events.md"
Write-Host ""
