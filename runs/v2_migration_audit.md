# V2 迁移审计报告

> 生成时间: 2026-06-19
> 审计范围: 全量文件（V1 旧管线 + V2 Day 1 MVP）

---

## 一、V1 旧管线资产盘点

### 可保留（V2 直接复用）

| 文件 | 原因 |
|------|------|
| `src/common.py` | **核心基础**。ADB 工具函数、路径约定、JSON I/O。V2 所有模块都 import 它，不动。 |
| `config/event_rules.json` | 关键词库质量高（40+ 反应词、20+ 分享词），V2 评分引擎可读取。 |
| `config/wechat_groups.json` | ADB 设备配置 + 群信息，V2 通过 common.py 间接读取。 |
| `prompts/01-extract.md` ~ `06-next-week-plan.md` | 6 个成稿 prompt，Day 1 后交给 AI 用。不动。 |
| `scripts/generate_digest.py` | DeepSeek/Claude API 调用，Day 1 后阶段使用。不动。 |
| `requirements.txt` | Pillow + pytesseract，V2 也需要。 |
| `product-brief.md` / `quality-bar.md` / `references.md` | 产品定义文档，不动。 |
| `.gitignore` | 不动。 |

### 可废弃（标记为 legacy，不删除）

| 文件 | 原因 |
|------|------|
| `src/wechat_capture_bot.py` | V1 截图模块。多群嵌套结构，与 V2 `phone_capture.py` 功能重叠且格式不兼容。 |
| `src/ocr_extract.py` | V1 OCR 模块。依赖 V1 manifest 的 sha256 索引 + `ocr_cache.json` 格式。V2 用 `ocr_pipeline.py` 替代。 |
| `src/event_detector.py` | V1 事件检测。依赖 V1 manifest + ocr_cache 格式，三种事件类型的滑窗检测逻辑复杂。V2 用截图级热度评分 + `event_builder.py` 替代。 |
| `src/build_manifest.py` | V1 manifest 构建器。扫描 `inbox/adb_captures/` 目录，V2 不用这个路径。 |
| `src/weekly_pipeline.py` | V1 编排器。串联 V1 三个模块，V2 用 `ip_highlight_cli.py` 替代。 |
| `scripts/run_phone_bot.ps1` | V1 PowerShell 入口。V2 用 `run_ip_highlight_day1.cmd` 替代。 |
| `scripts/build_candidate_events.ps1` | V1 手动截图入口。V2 用 `python -m src.ip_highlight_cli ocr --week ...` 替代。 |
| `run_local_bot_0api.cmd` | V1 一键入口（如存在）。V2 用 `run_ip_highlight_day1.cmd` 替代。 |
| `run_hybrid_digest.cmd` | API 成稿入口（如存在）。暂不需要，Day 1 不调 API。 |

### 不确定（暂保留观察）

| 文件 | 原因 |
|------|------|
| `BOT_PROOF.md` / `PHONE_BOT_QUICKSTART.md` / `AI_HANDOFF.md` | V1 文档，内容部分过时但有参考价值。暂保留。 |
| `CLAUDE_DEEPSEEK_QUICKSTART.md` | API 接入说明。Day 1 不用，后续阶段可能参考。 |
| `runs/2026-W24/` 原有数据 | V1 格式的样本数据。作为测试参考保留，V2 会生成自己的新数据。 |
| `inbox/adb_captures/` | V1 截图存放位置。V2 存到 `runs/{week}/screenshots/`，旧目录保留但不再写入。 |
| `outputs/` / `knowledge/` | 上一轮生成的成品。保留。 |

---

## 二、当前最大卡点

### 为什么 candidate_events.md 曾经是 0

根本原因链：

1. **OCR 未真跑**：`ocr_cache.json` 标注为"缓存（已预填）"——是手工填入的示范数据，不是 Tesseract 实跑
2. **Tesseract 未安装**：云端环境和本地 Windows 都缺 Tesseract + chi_sim 语言包
3. **静默降级**：V1 `ocr_extract.py` 在 Tesseract 不可用时生成 `manual_ocr_template.md`（空模板），用户没填 → ocr_cache 为空 → event_detector 读到 0 行文本 → 0 候选

**V2 的解决**：`ocr_pipeline.py` 在 Tesseract 不可用时明确报错并生成空白 `ocr_text.md`，不会静默吞掉错误。同时生成 `ocr_health_report.md` 让用户一眼看到哪张截图 OCR 失败。

---

## 三、V1 与 V2 架构对比

```
V1 流程（多群嵌套、sha256 索引）:
  wechat_capture_bot.py → inbox/adb_captures/{week}/{group}/
       ↓
  build_manifest.py → capture_manifest.json（per-group screens + sha256）
       ↓
  ocr_extract.py → ocr_cache.json（sha256 → text）+ ocr_text.md
       ↓
  event_detector.py → candidate_events.md + event_scores.json


V2 流程（单群扁平、文件名索引）:
  phone_capture.py → runs/{week}/screenshots/001.png ...
       ↓                 ↓
       ↓            capture_manifest.json（flat paths list）
       ↓
  ocr_pipeline.py → ocr_text.md + ocr_health_report.md
       ↓
  highlight_scoring_engine.py → screenshot_heat_scores.json + review_queue.md
       ↓
  event_builder.py → candidate_events.md + manual_candidate_events.md
```

**关键差异**：
- V1 用 sha256 做截图索引，V2 用文件名（001.png, 002.png ...）
- V1 是事件级检测（滑窗匹配触发词+响应），V2 是截图级热度评分（更稳健）
- V1 支持多群+跨群检测，V2 只做单群（Day 1 足够）
- V2 新增 `ocr_health_report.md` 和 `review_queue.md`（V1 没有）

---

## 四、V2 重建方案

### 已完成的 V2 文件

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/ip_highlight_cli.py` | ✅ 已创建 | 统一 CLI，6 个子命令 |
| `src/phone_capture.py` | ✅ 已创建 | ADB 截图采集 |
| `src/ocr_pipeline.py` | ✅ 已创建 | OCR + 健康报告 |
| `src/highlight_scoring_engine.py` | ✅ 已创建 | 截图热度评分 |
| `src/event_builder.py` | ✅ 已创建 | 候选事件构建 |
| `config/ip_highlight.yaml.example` | ✅ 已创建 | 配置示例 |
| `run_ip_highlight_day1.cmd` | ✅ 已创建 | Windows 一键入口 |
| `docs/IP_HIGHLIGHT_DAY1.md` | ✅ 已创建 | 使用说明 |

### 待修补

1. V1 旧文件需要标记为 legacy（加说明，不删除）
2. V2 模块间接口需要验证端到端（已在上轮用测试数据验证通过）

---

## 五、运行指南

```cmd
cd C:\Users\mings\Documents\ip群周精华总结

REM 一键全流程
run_ip_highlight_day1.cmd 2026-W25

REM 或分步运行
python -m src.ip_highlight_cli doctor       --week 2026-W25
python -m src.ip_highlight_cli capture      --week 2026-W25
python -m src.ip_highlight_cli ocr          --week 2026-W25
python -m src.ip_highlight_cli score        --week 2026-W25
python -m src.ip_highlight_cli build-events --week 2026-W25
```

### 成功后应该看到

```
runs/2026-W25/
  screenshots/          ← 40-80 张 PNG
  capture_manifest.json ← 截图清单
  ocr_text.md           ← OCR 文本
  ocr_health_report.md  ← OCR 质量报告
  screenshot_heat_scores.json ← 热度评分
  review_queue.md       ← 高热截图排行
  candidate_events.md   ← 候选事件
  manual_candidate_events.md  ← 人工补充模板
```
