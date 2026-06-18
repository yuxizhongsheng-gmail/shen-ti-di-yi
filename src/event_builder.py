#!/usr/bin/env python3
"""IP 群高光 · Day 1 候选事件构建器

根据 review_queue / screenshot_heat_scores / ocr_text 生成候选事件。
不调用任何 LLM API。

用法：
    python src/event_builder.py --week 2026-W24
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import common

EVENT_TYPES = [
    "群友提问",
    "方法论",
    "案例复盘",
    "争议讨论",
    "行动建议",
    "群友作品",
    "资源推荐",
]

TYPE_INDICATORS = {
    "群友提问": ["?", "？", "怎么", "如何", "为什么", "求问", "请问"],
    "方法论": ["方法", "步骤", "思路", "流程", "框架", "策略", "模型"],
    "案例复盘": ["复盘", "案例", "实操", "实测", "数据", "结果", "效果"],
    "争议讨论": ["不同意", "但是", "不过", "其实", "反而", "未必"],
    "行动建议": ["建议", "应该", "可以试", "推荐", "值得"],
    "群友作品": ["分享", "我写的", "我做的", "发布", "上线", "链接"],
    "资源推荐": ["工具", "推荐", "资源", "模板", "教程", "课程"],
}


def load_ocr_text(week: str) -> dict[str, str]:
    """Parse ocr_text.md."""
    ocr_path = common.week_dir(week) / "ocr_text.md"
    if not ocr_path.exists():
        return {}

    content = ocr_path.read_text(encoding="utf-8")
    results: dict[str, str] = {}
    current_file = None
    in_code = False
    lines_buf: list[str] = []

    for line in content.splitlines():
        if line.startswith("## ") and line.endswith(".png"):
            if current_file and lines_buf:
                results[current_file] = "\n".join(lines_buf)
            current_file = line[3:].strip()
            lines_buf = []
            in_code = False
        elif line.strip() == "```":
            in_code = not in_code
        elif in_code and current_file:
            lines_buf.append(line)

    if current_file and lines_buf:
        results[current_file] = "\n".join(lines_buf)
    return results


def load_heat_scores(week: str) -> dict:
    """Load screenshot_heat_scores.json."""
    path = common.week_dir(week) / "screenshot_heat_scores.json"
    if not path.exists():
        return {}
    return common.load_json(path)


def guess_event_type(text: str) -> str:
    """Guess event type from text content."""
    best_type = "群友提问"
    best_count = 0
    for etype, indicators in TYPE_INDICATORS.items():
        count = sum(1 for kw in indicators if kw in text)
        if count > best_count:
            best_count = count
            best_type = etype
    return best_type


def extract_key_quotes(text: str, max_quotes: int = 5) -> list[str]:
    """Extract the most substantive lines as key quotes."""
    lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 10]
    scored = []
    for line in lines:
        score = len(line)
        if ":" in line or "：" in line:
            score += 20
        if any(c in line for c in "?？"):
            score += 10
        scored.append((score, line))
    scored.sort(reverse=True)
    return [line for _, line in scored[:max_quotes]]


def guess_title(text: str, keywords: list[str]) -> str:
    """Generate a short title from text content."""
    for line in text.splitlines():
        line = line.strip()
        if len(line) > 15 and any(kw in line for kw in keywords):
            if ":" in line or "：" in line:
                _, _, after = line.partition(":" if ":" in line else "：")
                after = after.strip()
                if len(after) > 8:
                    return after[:40]
            return line[:40]
    return "需要人工命名"


def build_events(week: str, config: dict) -> tuple[list[dict], int]:
    """Build candidate events from OCR text and heat scores."""
    ocr_data = load_ocr_text(week)
    heat_data = load_heat_scores(week)

    if not ocr_data:
        print(f"❌ 无 OCR 数据。请先运行 OCR: python src/ocr_pipeline.py --week {week}")
        sys.exit(1)

    scores = heat_data.get("scores", {})
    clusters = heat_data.get("hot_clusters", [])

    candidate_th = config.get("candidate_threshold", 50)
    kw_list = config.get("highlight_keywords", [
        "IP", "定位", "朋友圈", "成交", "流量", "内容", "复盘",
        "私域", "产品", "用户", "变现", "案例", "选题", "认知",
        "方法", "训练营", "小红书", "抖音", "账号",
    ])

    events: list[dict] = []
    used_screenshots: set[str] = set()

    for cl in clusters:
        fnames = cl["screenshots"]
        merged_text = "\n".join(ocr_data.get(f, "") for f in fnames)
        if not merged_text.strip():
            continue

        event = {
            "screenshots": fnames,
            "range": cl["range"],
            "group": config.get("main_group", "25IP训练营交流群"),
            "type": guess_event_type(merged_text),
            "heat_score": cl["max_score"],
            "keywords": cl["keywords"],
            "title": guess_title(merged_text, kw_list),
            "key_quotes": extract_key_quotes(merged_text),
            "text_preview": merged_text[:500],
        }
        events.append(event)
        used_screenshots.update(fnames)

    for fname in sorted(scores.keys()):
        if fname in used_screenshots:
            continue
        s = scores[fname]
        if s["total"] < candidate_th:
            continue
        text = ocr_data.get(fname, "")
        if not text.strip():
            continue
        event = {
            "screenshots": [fname],
            "range": fname,
            "group": config.get("main_group", "25IP训练营交流群"),
            "type": guess_event_type(text),
            "heat_score": s["total"],
            "keywords": s.get("keyword_hits", []),
            "title": guess_title(text, kw_list),
            "key_quotes": extract_key_quotes(text),
            "text_preview": text[:500],
        }
        events.append(event)

    events.sort(key=lambda e: e["heat_score"], reverse=True)

    _write_candidate_events(week, events, config)
    _write_manual_template(week, events, ocr_data)

    return events, len(ocr_data)


def _write_candidate_events(week: str, events: list[dict], config: dict) -> None:
    must_review_th = config.get("must_review_threshold", 70)

    lines = [
        f"# {week} 候选高光事件",
        "",
        f"> 自动生成于 {common.now_iso()}",
        f"> 共 {len(events)} 条候选事件",
        "> 不调用任何 LLM API，纯本地规则生成",
        "",
    ]

    if not events:
        lines += [
            "## ⚠️ 未检测到候选事件",
            "",
            "可能原因：",
            "- OCR 文本质量不足",
            "- 截图未涵盖有价值的讨论",
            "- 评分阈值过高",
            "",
            "建议：",
            "1. 查看 ocr_health_report.md 确认 OCR 质量",
            "2. 查看 review_queue.md 手动筛选",
            "3. 编辑 manual_candidate_events.md 手工补充",
            "",
        ]
    else:
        for i, ev in enumerate(events, 1):
            level = "A" if ev["heat_score"] >= must_review_th else "B" if ev["heat_score"] >= 50 else "C"
            lines += [
                f"## EVENT-{i:03d}: {ev['title']}",
                "",
                f"- 来源截图: {ev['range']}",
                f"- 群聊: {ev['group']}",
                f"- 事件类型: {ev['type']}",
                f"- 热度分: {ev['heat_score']}",
                f"- 推荐级别: {level}",
                "",
                "### 1. 事件背景",
                "",
                f"在 {ev['group']} 群内，截图 {ev['range']} 记录了一段关于"
                f"{'、'.join(ev['keywords'][:3]) or '待确认主题'}的讨论。"
                "（以下内容由 OCR 自动提取，可能存在识别误差，请对照原始截图确认。）",
                "",
                "### 2. 关键原话",
                "",
            ]
            for q in ev["key_quotes"]:
                lines.append(f"> {q}")
                lines.append("")
            if not ev["key_quotes"]:
                lines.append("> （OCR 未提取到足够清晰的原话，需要人工补充）")
                lines.append("")

            lines += [
                "### 3. 讨论过程",
                "",
                "（需要人工补充：对照截图还原讨论脉络）",
                "",
                "### 4. 可沉淀价值",
                "",
                "（需要人工补充：这段讨论对群友最大的价值是什么？）",
                "",
                "### 5. 可写成周刊角度",
                "",
                "（需要人工补充：如果要写进周刊，建议从什么角度切入？）",
                "",
                "---",
                "",
            ]

    out = common.week_dir(week) / "candidate_events.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✅ candidate_events.md: {out}")


def _write_manual_template(week: str, events: list[dict], ocr_data: dict) -> None:
    lines = [
        f"# {week} 人工补充候选事件模板",
        "",
        "> 如果自动检测的候选事件不够或质量不足，请在这里手动补充。",
        "> 格式与 candidate_events.md 一致。",
        "",
    ]

    if events:
        lines += [
            f"自动检测到 {len(events)} 条候选。如果你认为有遗漏，请在下方补充。",
            "",
        ]
    else:
        lines += [
            "⚠️ 自动检测未产出候选事件。请根据 review_queue.md 手动筛选并在下方填写。",
            "",
        ]

    lines += [
        "## EVENT-M01: （请填写事件标题）",
        "",
        "- 来源截图: （请填写，如 013.png - 016.png）",
        "- 群聊: 25IP训练营交流群",
        "- 事件类型: 群友提问 / 方法论 / 案例复盘 / 争议讨论 / 行动建议",
        "- 热度分: （参考 screenshot_heat_scores.json）",
        "- 推荐级别: A / B / C",
        "",
        "### 1. 事件背景",
        "",
        "（请填写）",
        "",
        "### 2. 关键原话",
        "",
        "> （请从截图中摘录原话）",
        "",
        "### 3. 讨论过程",
        "",
        "（请填写）",
        "",
        "### 4. 可沉淀价值",
        "",
        "（请填写）",
        "",
        "### 5. 可写成周刊角度",
        "",
        "（请填写）",
        "",
        "---",
        "",
        "## EVENT-M02: （请填写事件标题）",
        "",
        "（同上格式）",
        "",
    ]

    out = common.week_dir(week) / "manual_candidate_events.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ manual_candidate_events.md: {out}")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="IP 群高光 · 候选事件构建")
    p.add_argument("--week", required=True)
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    from phone_capture import load_yaml_config
    config = load_yaml_config()
    events, total = build_events(args.week, config)
    print(f"\n📊 结果: {len(events)} 条候选事件（共 {total} 张截图）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
