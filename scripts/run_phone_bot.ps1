# IP 群高光 · 手机微信 Bot 全流程入口（0 API 消耗）
#
# ─── 安全承诺（默认行为，无需 .env / API 密钥）──────────────────────────
#   ✅ 全程 0 API 消耗          不调用 Claude / DeepSeek / GPT 等任何模型
#   ✅ 不读取微信数据库          只截取手机屏幕当前可见内容
#   ✅ 不自动发送微信消息        操作仅限截图 + 滚动（input swipe）
#   ✅ 不上传截图到任何服务器    截图只保存在本地 inbox\adb_captures\
#   ✅ 只在本地生成文件          所有产出在 runs\<week>\ 下
# ─────────────────────────────────────────────────────────────────────────
#
# 用法：
#   .\scripts\run_phone_bot.ps1 -Week 2026-W24
#   .\scripts\run_phone_bot.ps1 -Week 2026-W24 -Groups main
#   .\scripts\run_phone_bot.ps1 -Week 2026-W24 -Backfill 2026-06-07
#   .\scripts\run_phone_bot.ps1 -Week 2026-W24 -Force       # 忽略 completed 标记，重新采集
#
# 前置准备（一次性）：
#   1. adb.exe 放入 tools\platform-tools\  （见 tools\adb-setup.md）
#   2. 手机开启 USB 调试，用数据线连接电脑，点手机弹窗「允许调试」
#   3. （可选）安装 Tesseract-OCR 提升 OCR 精度（见 src\ocr_extract.py 顶部）
#
# 产出（runs\<week>\ 下）：
#   capture_manifest.json   截图清单（可断点续采）
#   ocr_text.md             OCR 文本（无 Tesseract 则生成手动模板）
#   event_scores.json       候选事件评分（纯关键词规则，0 API）
#   candidate_events.md     候选高光事件（交给 Claude 做精筛，再调用模型）

param(
    [Parameter(Mandatory=$true)][string]$Week,
    [switch]$Force,
    [string]$Groups,    # 只采集指定群，如 "main" 或 "main,trigger"
    [string]$Backfill   # 补采日期，如 "2026-06-07"
    # 注意：无 -UseApiOcr 参数。本脚本全程 0 API。
    # 如需 API OCR（需要 ANTHROPIC_API_KEY），请直接调用：
    #   python src/ocr_extract.py --week $Week --api-ocr
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# ── 安全声明 ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "===== IP 群高光 · 手机 Bot · $Week =====" -ForegroundColor Cyan
Write-Host "  0 API | 不读微信DB | 不发消息 | 不上传截图 | 只生成本地文件" -ForegroundColor DarkGreen
Write-Host ""

# ── Step 1: ADB 采集 ──────────────────────────────────────────────────
# wechat_capture_bot.py 内部会：
#   1) 检查 adb devices
#   2) 把微信切到前台（adb shell monkey）
#   3) 提示你手动进入目标群，按 Enter 开始
#   4) 自动截图 + 滚动，截图保存到 inbox\adb_captures\<week>\<group>\
#   5) 写 runs\<week>\capture_manifest.json（断点续采）
Write-Host "[1/3] ADB 截图采集  ->  inbox\adb_captures\$Week\" -ForegroundColor Yellow
Write-Host "  Bot 会提示你在手机上打开微信目标群，按 Enter 开始自动截图。"
Write-Host ""

$captureArgs = @("src/wechat_capture_bot.py", "--week", $Week)
if ($Force)   { $captureArgs += "--force" }
if ($Groups)  { $captureArgs += "--groups"; $captureArgs += $Groups }
if ($Backfill){ $captureArgs += "--backfill"; $captureArgs += $Backfill }

python @captureArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  ⚠️  采集步骤异常退出（退出码 $LASTEXITCODE）。" -ForegroundColor Red
    Write-Host "  常见原因："
    Write-Host "    • adb.exe 未放在 tools\platform-tools\（见 tools\adb-setup.md）"
    Write-Host "    • 手机未连接，或未开启 USB 调试，或未点「允许此电脑调试」"
    Write-Host "    • 你按了 Ctrl+C 中断（进度已保存，重新运行可断点续采）"
    Write-Host ""
    Write-Host "  调试：在终端运行 adb devices，应能看到你的设备序列号。"
    exit 1
}

# ── Step 2: 本地 OCR（默认 0 API）────────────────────────────────────
Write-Host ""
Write-Host "[2/3] 本地 OCR  ->  runs\$Week\ocr_text.md" -ForegroundColor Yellow
Write-Host "  使用本地 Tesseract（0 API）。未安装 Tesseract 时生成手动填写模板。"

python src/ocr_extract.py --week $Week
$ocrExit = $LASTEXITCODE

if ($ocrExit -eq 1) {
    Write-Host ""
    Write-Host "  ℹ️  本地 OCR 不可用——已生成手动填写模板。" -ForegroundColor DarkYellow
    Write-Host ""
    Write-Host "  接下来两个选项，任选其一："
    Write-Host "  选项 A（推荐）：安装 Tesseract-OCR"
    Write-Host "    见 src\ocr_extract.py 顶部说明，或 tools\adb-setup.md"
    Write-Host "    安装后重新运行此脚本即可。"
    Write-Host ""
    Write-Host "  选项 B：手动填写模板"
    Write-Host "    打开 runs\$Week\manual_ocr_template.md"
    Write-Host "    在每张截图的 <!-- OCR BEGIN --> 和 <!-- OCR END --> 之间"
    Write-Host "    抄写截图中的聊天文字，然后重新运行此脚本。"
    Write-Host ""
    Write-Host "  截图保存位置：inbox\adb_captures\$Week\"
    exit 1
}
if ($ocrExit -ne 0) {
    Write-Host "  ⚠️  OCR 步骤出错（退出码 $ocrExit），请检查上方错误。" -ForegroundColor Red
    exit 1
}

# ── Step 3: 本地规则初筛（0 API）────────────────────────────────────
Write-Host ""
Write-Host "[3/3] 规则初筛  ->  runs\$Week\candidate_events.md" -ForegroundColor Yellow
Write-Host "  纯关键词 + 参与人数 + 回复密度评分，0 API。"

python src/event_detector.py --week $Week
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ⚠️  规则初筛出错（退出码 $LASTEXITCODE），请检查上方错误。" -ForegroundColor Red
    exit 1
}

# ── 完成 ──────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "===== ✅ 全部完成，全程 0 API 消耗 =====" -ForegroundColor Green
Write-Host ""
Write-Host "  产出文件（runs\$Week\）："
Write-Host "    capture_manifest.json    截图清单"
Write-Host "    ocr_text.md              OCR 文本"
Write-Host "    event_scores.json        候选事件评分"
Write-Host "    candidate_events.md      候选高光事件  ← 重点看这个"
Write-Host ""
Write-Host "  下一步（此处才开始用模型）："
Write-Host "    把 candidate_events.md 交给 Claude，"
Write-Host "    配合 prompts\01-extract.md 做 A/B/C 精筛。"
Write-Host ""
