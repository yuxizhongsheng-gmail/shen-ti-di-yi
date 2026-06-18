#!/usr/bin/env python3
"""IP 群高光 · Day 1 Bot CLI

统一命令行入口，串联截图→OCR→评分→候选事件全流程。
不调用任何 LLM API。

用法：
    python -m src.ip_highlight_cli doctor  --week 2026-W24
    python -m src.ip_highlight_cli capture --week 2026-W24
    python -m src.ip_highlight_cli ocr     --week 2026-W24
    python -m src.ip_highlight_cli score   --week 2026-W24
    python -m src.ip_highlight_cli build-events --week 2026-W24
    python -m src.ip_highlight_cli day1    --week 2026-W24

    day1 = doctor → capture → ocr → score → build-events（一键全流程）
"""
from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common
from phone_capture import load_yaml_config, doctor as run_doctor, capture as run_capture
from ocr_pipeline import run_ocr
from highlight_scoring_engine import run_scoring
from event_builder import build_events


BANNER = r"""
╔══════════════════════════════════════════════╗
║       IP 群高光 · Day 1 Bot                  ║
║       本地自动化采集 · 0 API                  ║
╚══════════════════════════════════════════════╝
"""


def cmd_doctor(args):
    """检查 ADB 连接和手机状态。"""
    config = load_yaml_config()
    try:
        adb_path, serial, screen = run_doctor(config)
        print(f"\n✅ 一切就绪！")
        print(f"   ADB:    {adb_path}")
        print(f"   设备:   {serial}")
        print(f"   分辨率: {screen[0]}x{screen[1]}")
        return 0
    except common.AdbError as e:
        print(f"\n❌ {e}", file=sys.stderr)
        return 1


def cmd_capture(args):
    """执行 ADB 截图采集。"""
    config = load_yaml_config()
    try:
        run_capture(args.week, config, args.count, args.delay)
        return 0
    except common.AdbError as e:
        print(f"\n❌ {e}", file=sys.stderr)
        return 1


def cmd_ocr(args):
    """对截图执行 OCR。"""
    config = load_yaml_config()
    run_ocr(args.week, config, args.force)
    return 0


def cmd_score(args):
    """对截图做热度评分。"""
    config = load_yaml_config()
    scores, clusters = run_scoring(args.week, config)
    hot = sum(1 for s in scores.values() if s["total"] >= 50)
    print(f"\n📊 {len(scores)} 张截图已评分，{hot} 张达到候选阈值，{len(clusters)} 个热点区间")
    return 0


def cmd_build_events(args):
    """构建候选事件。"""
    config = load_yaml_config()
    events, total = build_events(args.week, config)
    print(f"\n📊 {len(events)} 条候选事件（共 {total} 张截图）")
    return 0


def cmd_day1(args):
    """一键执行全流程: doctor → capture → ocr → score → build-events"""
    print(BANNER)
    print(f"🗓  周次: {args.week}")
    print(f"📁 输出: runs/{args.week}/")
    print()

    config = load_yaml_config()
    week = args.week

    # Step 1: Doctor
    print("=" * 50)
    print("  步骤 1/5: 检查 ADB 连接")
    print("=" * 50)
    try:
        adb_path, serial, screen = run_doctor(config)
    except common.AdbError as e:
        print(f"\n❌ ADB 检查失败: {e}", file=sys.stderr)
        print("\n请确认：")
        print("  1. 手机用 USB 线连接电脑")
        print("  2. 手机开启了「开发者选项 → USB 调试」")
        print("  3. 手机上点击了「允许此电脑调试」")
        print("  4. adb.exe 在 tools/platform-tools/ 下或系统 PATH 中")
        return 1

    # Step 2: Capture
    print()
    print("=" * 50)
    print("  步骤 2/5: 截图采集")
    print("=" * 50)
    try:
        run_capture(week, config, args.count, args.delay)
    except common.AdbError as e:
        print(f"\n❌ 截图采集失败: {e}", file=sys.stderr)
        return 1

    # Step 3: OCR
    print()
    print("=" * 50)
    print("  步骤 3/5: OCR 文字识别")
    print("=" * 50)
    run_ocr(week, config)

    # Step 4: Score
    print()
    print("=" * 50)
    print("  步骤 4/5: 截图热度评分")
    print("=" * 50)
    scores, clusters = run_scoring(week, config)

    # Step 5: Build Events
    print()
    print("=" * 50)
    print("  步骤 5/5: 构建候选事件")
    print("=" * 50)
    events, total = build_events(week, config)

    # Summary
    print()
    print("=" * 50)
    print("  🎉 Day 1 Bot 全流程完成！")
    print("=" * 50)
    print()
    run_dir = common.week_dir(week)
    print(f"  📁 输出目录: {run_dir}")
    print()

    expected_files = [
        ("screenshots/", "截图文件"),
        ("capture_manifest.json", "截图清单"),
        ("ocr_text.md", "OCR 文本"),
        ("ocr_health_report.md", "OCR 健康报告"),
        ("screenshot_heat_scores.json", "热度评分"),
        ("review_queue.md", "复查清单"),
        ("candidate_events.md", "候选事件"),
        ("manual_candidate_events.md", "人工补充模板"),
    ]

    for fname, desc in expected_files:
        p = run_dir / fname
        exists = p.exists()
        icon = "✅" if exists else "❌"
        print(f"  {icon} {fname:40s} {desc}")

    hot = sum(1 for s in scores.values() if s["total"] >= 50)
    print()
    print(f"  📊 截图: {total} 张 | 高热: {hot} 张 | 热点区间: {len(clusters)} 个 | 候选事件: {len(events)} 条")
    print()

    if events:
        print("  下一步：")
        print(f"    1. 打开 runs/{week}/review_queue.md 查看高热截图")
        print(f"    2. 打开 runs/{week}/candidate_events.md 审阅候选事件")
        print(f"    3. 如需补充，编辑 runs/{week}/manual_candidate_events.md")
        print(f"    4. 确认后，可将 candidate_events.md 交给 Claude/DeepSeek 生成周刊")
    else:
        print("  ⚠️  未生成候选事件。可能原因：")
        print("    - OCR 质量不足（检查 ocr_health_report.md）")
        print("    - 截图未涵盖有价值内容")
        print(f"    - 请编辑 runs/{week}/manual_candidate_events.md 手工补充")

    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ip_highlight_cli",
        description="IP 群高光 · Day 1 Bot CLI",
    )
    sub = parser.add_subparsers(dest="command", help="子命令")

    # doctor
    p_doc = sub.add_parser("doctor", help="检查 ADB 连接")
    p_doc.add_argument("--week", default="2026-W25")

    # capture
    p_cap = sub.add_parser("capture", help="截图采集")
    p_cap.add_argument("--week", required=True)
    p_cap.add_argument("--count", type=int, default=None)
    p_cap.add_argument("--delay", type=float, default=None)

    # ocr
    p_ocr = sub.add_parser("ocr", help="OCR 文字识别")
    p_ocr.add_argument("--week", required=True)
    p_ocr.add_argument("--force", action="store_true")

    # score
    p_score = sub.add_parser("score", help="截图热度评分")
    p_score.add_argument("--week", required=True)

    # build-events
    p_build = sub.add_parser("build-events", help="构建候选事件")
    p_build.add_argument("--week", required=True)

    # day1
    p_day1 = sub.add_parser("day1", help="一键全流程")
    p_day1.add_argument("--week", required=True)
    p_day1.add_argument("--count", type=int, default=None)
    p_day1.add_argument("--delay", type=float, default=None)

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "doctor": cmd_doctor,
        "capture": cmd_capture,
        "ocr": cmd_ocr,
        "score": cmd_score,
        "build-events": cmd_build_events,
        "day1": cmd_day1,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
