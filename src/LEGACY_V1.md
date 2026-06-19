# V1 旧管线模块说明

以下文件属于 V1 管线，已被 V2 Day 1 MVP 替代。
**不要删除**，保留作为参考和回退选项。

## V1 模块 → V2 替代

| V1 文件 | V2 替代 | 说明 |
|---------|---------|------|
| `wechat_capture_bot.py` | `phone_capture.py` | 截图采集。V1 多群嵌套，V2 单群扁平 |
| `ocr_extract.py` | `ocr_pipeline.py` | OCR。V2 新增 health report |
| `event_detector.py` | `highlight_scoring_engine.py` + `event_builder.py` | V1 事件级检测，V2 截图级评分 |
| `build_manifest.py` | `phone_capture.py` | manifest 构建。V2 内置 |
| `weekly_pipeline.py` | `ip_highlight_cli.py` | 编排器。V2 用 CLI 子命令 |

## 仍在使用的共享模块

- `common.py` — V1 和 V2 共用，不要改动

## 如果需要回退到 V1

```cmd
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_phone_bot.ps1 -Week 2026-W25
```
