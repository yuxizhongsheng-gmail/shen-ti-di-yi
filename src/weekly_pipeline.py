#!/usr/bin/env python3
"""IP 群高光 · 每周流水线（采集 -> OCR -> 规则检测）

把 wechat_capture_bot / ocr_extract / event_detector 串起来一次性跑完。
不在这里生成周刊 —— 周刊由 Claude/GPT 配合 prompts/02-weekly-digest.md 完成。
这个脚本的产出是"候选高光"，是给模型的输入，不是给读者的成品。

用法：
    python src/weekly_pipeline.py --week 2026-W24
    python src/weekly_pipeline.py --week 2026-W24 --skip-capture   # 截图已采集好，只跑 OCR+检测
    python src/weekly_pipeline.py --week 2026-W24 --skip-capture --skip-ocr  # 只重新跑规则检测
"""

from __future__ import annotations

import argparse
import sys

import common
import event_detector
import ocr_extract
import wechat_capture_bot


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="串联 采集 -> OCR -> 规则检测")
    parser.add_argument("--week", required=True, help="周数，如 2026-W24")
    parser.add_argument("--groups", help="传递给采集步骤：只采集指定的群 id，逗号分隔")
    parser.add_argument("--backfill", help="传递给采集步骤：补采指定日期 YYYY-MM-DD")
    parser.add_argument("--max-screens", type=int, help="传递给采集步骤：覆盖单群最大截图数")
    parser.add_argument("--force-capture", action="store_true", help="采集步骤忽略 completed 状态重新采集")
    parser.add_argument("--force-ocr", action="store_true", help="OCR 步骤忽略缓存全部重新识别")
    parser.add_argument("--skip-capture", action="store_true", help="跳过采集（截图已准备好）")
    parser.add_argument("--skip-ocr", action="store_true", help="跳过 OCR（ocr_cache.json 已存在）")
    parser.add_argument("--skip-detect", action="store_true", help="跳过事件检测")
    parser.add_argument("--config", default=str(common.DEFAULT_CONFIG_PATH), help="配置文件路径")
    parser.add_argument("--rules", default=str(common.DEFAULT_RULES_PATH), help="事件规则文件路径")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    week = args.week

    if not args.skip_capture:
        capture_argv = ["--week", week, "--config", args.config]
        if args.groups:
            capture_argv += ["--groups", args.groups]
        if args.backfill:
            capture_argv += ["--backfill", args.backfill]
        if args.max_screens:
            capture_argv += ["--max-screens", str(args.max_screens)]
        if args.force_capture:
            capture_argv += ["--force"]
        print("\n========== 步骤 1/3：采集（需要操作手机） ==========")
        rc = wechat_capture_bot.main(capture_argv)
        if rc != 0:
            print("[pipeline] 采集步骤失败，流水线停止。", file=sys.stderr)
            return rc
    else:
        print("\n========== 步骤 1/3：采集（已跳过） ==========")

    if not args.skip_ocr:
        ocr_argv = ["--week", week, "--config", args.config]
        if args.force_ocr:
            ocr_argv += ["--force"]
        print("\n========== 步骤 2/3：本地 OCR ==========")
        rc = ocr_extract.main(ocr_argv)
        if rc != 0:
            print("[pipeline] OCR 步骤未完成（见上方提示），流水线停止。", file=sys.stderr)
            return rc
    else:
        print("\n========== 步骤 2/3：本地 OCR（已跳过） ==========")

    if not args.skip_detect:
        detect_argv = ["--week", week, "--config", args.config, "--rules", args.rules]
        print("\n========== 步骤 3/3：规则检测 ==========")
        rc = event_detector.main(detect_argv)
        if rc != 0:
            print("[pipeline] 事件检测步骤失败，流水线停止。", file=sys.stderr)
            return rc
    else:
        print("\n========== 步骤 3/3：规则检测（已跳过） ==========")

    print("\n" + "=" * 60)
    print(f"流水线完成 · {week}")
    print(f"候选高光：{common.candidate_events_path(week)}")
    print(f"结构化数据：{common.event_scores_path(week)}")
    print()
    print("下一步（需要 GPT/Claude，从这里开始才消耗模型额度）：")
    print(f"  1. 把 candidate_events.md + inbox/{week}-raw.md 一起交给 Claude")
    print("  2. 用 prompts/01-extract.md 做 A/B/C 精筛")
    print("  3. 依次跑 prompts/02~06，生成周刊 / 短版 / 知识沉淀 / 下周计划")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
