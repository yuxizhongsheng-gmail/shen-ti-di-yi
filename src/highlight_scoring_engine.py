#!/usr/bin/env python3
"""IP 群高光 · Day 1 截图热度评分引擎

根据 OCR 文本给每张截图打热度分，找出高价值截图区间。
不调用任何 LLM API。

用法：
    python src/highlight_scoring_engine.py --week 2026-W24
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import common

HIGHLIGHT_KEYWORDS = [
    "IP", "定位", "朋友圈", "成交", "流量", "内容", "复盘",
    "私域", "产品", "用户", "变现", "案例", "选题", "认知",
    "方法", "训练营", "小红书", "抖音", "账号",
]

RESPONSE_KEYWORDS = [
    "对", "确实", "学到了", "有用", "展开讲讲", "我也是",
    "赞", "牛", "可以", "这个很重要", "原来如此", "收藏",
    "厉害", "太强了", "已收藏", "棒", "绝了", "mark",
    "+1", "受教了", "好实用", "太有用了",
]

DEFAULT_WEIGHTS = {
    "text_length_weight": 1.0,
    "keyword_weight": 3.0,
    "question_weight": 2.0,
    "long_text_weight": 1.5,
    "response_weight": 2.0,
    "continuity_bonus": 1.5,
}

DEFAULT_CANDIDATE_THRESHOLD = 50
DEFAULT_MUST_REVIEW_THRESHOLD = 70


def load_ocr_text(week: str) -> dict[str, str]:
    """Parse ocr_text.md into {filename: text}."""
    ocr_path = common.week_dir(week) / "ocr_text.md"
    if not ocr_path.exists():
        print(f"❌ ocr_text.md 不存在: {ocr_path}")
        print(f"   请先运行: python src/ocr_pipeline.py --week {week}")
        sys.exit(1)

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


def score_screenshot(text: str, weights: dict, config: dict) -> dict:
    """Score a single screenshot's OCR text."""
    kw_list = config.get("highlight_keywords", HIGHLIGHT_KEYWORDS)
    resp_list = config.get("response_keywords", RESPONSE_KEYWORDS)
    w = {**DEFAULT_WEIGHTS, **(config.get("scoring") or {}), **weights}

    text_len = len(text)
    text_len_score = min(text_len / 200, 5.0) * w["text_length_weight"]

    kw_hits = [kw for kw in kw_list if kw in text]
    keyword_score = min(len(kw_hits) * 2, 10.0) * w["keyword_weight"]

    questions = len(re.findall(r"[?？]", text))
    question_score = min(questions * 2, 8.0) * w["question_weight"]

    long_lines = sum(1 for line in text.splitlines() if len(line.strip()) > 50)
    long_text_score = min(long_lines * 2, 6.0) * w["long_text_weight"]

    resp_hits = [kw for kw in resp_list if kw in text]
    response_score = min(len(resp_hits) * 1.5, 8.0) * w["response_weight"]

    total = round(text_len_score + keyword_score + question_score +
                  long_text_score + response_score, 1)

    return {
        "text_length": text_len,
        "text_length_score": round(text_len_score, 1),
        "keyword_hits": kw_hits,
        "keyword_score": round(keyword_score, 1),
        "questions": questions,
        "question_score": round(question_score, 1),
        "long_lines": long_lines,
        "long_text_score": round(long_text_score, 1),
        "response_hits": resp_hits,
        "response_score": round(response_score, 1),
        "total": total,
    }


def apply_continuity_bonus(scores: dict[str, dict], weights: dict, config: dict) -> None:
    """Add bonus when consecutive screenshots share keywords."""
    w = {**DEFAULT_WEIGHTS, **(config.get("scoring") or {}), **weights}
    bonus = w["continuity_bonus"]
    fnames = sorted(scores.keys())

    for i in range(1, len(fnames)):
        prev_kw = set(scores[fnames[i - 1]].get("keyword_hits", []))
        curr_kw = set(scores[fnames[i]].get("keyword_hits", []))
        overlap = prev_kw & curr_kw
        if overlap:
            b = round(min(len(overlap) * bonus, 5.0), 1)
            scores[fnames[i]]["continuity_keywords"] = list(overlap)
            scores[fnames[i]]["continuity_bonus"] = b
            scores[fnames[i]]["total"] = round(scores[fnames[i]]["total"] + b, 1)


def find_hot_clusters(scores: dict[str, dict], threshold: float) -> list[dict]:
    """Find contiguous runs of high-scoring screenshots."""
    fnames = sorted(scores.keys())
    clusters: list[dict] = []
    current: list[str] = []

    for f in fnames:
        if scores[f]["total"] >= threshold:
            current.append(f)
        else:
            if current:
                clusters.append(_make_cluster(current, scores))
                current = []
    if current:
        clusters.append(_make_cluster(current, scores))

    clusters.sort(key=lambda c: c["avg_score"], reverse=True)
    return clusters


def _make_cluster(fnames: list[str], scores: dict[str, dict]) -> dict:
    all_kw: set[str] = set()
    total_score = 0.0
    for f in fnames:
        all_kw.update(scores[f].get("keyword_hits", []))
        total_score += scores[f]["total"]
    return {
        "screenshots": fnames,
        "range": f"{fnames[0]} - {fnames[-1]}" if len(fnames) > 1 else fnames[0],
        "count": len(fnames),
        "avg_score": round(total_score / len(fnames), 1),
        "max_score": round(max(scores[f]["total"] for f in fnames), 1),
        "keywords": sorted(all_kw),
    }


def run_scoring(week: str, config: dict, weights: dict | None = None) -> tuple[dict, list]:
    """Score all screenshots and find hot clusters."""
    ocr_data = load_ocr_text(week)
    if not ocr_data:
        print("❌ ocr_text.md 中无截图文本")
        sys.exit(1)

    w = weights or {}
    scores: dict[str, dict] = {}
    for fname in sorted(ocr_data.keys()):
        scores[fname] = score_screenshot(ocr_data[fname], w, config)

    apply_continuity_bonus(scores, w, config)

    threshold = config.get("candidate_threshold", DEFAULT_CANDIDATE_THRESHOLD)
    clusters = find_hot_clusters(scores, threshold * 0.6)

    _write_scores_json(week, scores, clusters)
    _write_review_queue(week, scores, clusters, config)

    return scores, clusters


def _write_scores_json(week: str, scores: dict, clusters: list) -> None:
    out = common.week_dir(week) / "screenshot_heat_scores.json"
    common.write_json(out, {
        "week": week,
        "generated_at": common.now_iso(),
        "screenshot_count": len(scores),
        "scores": scores,
        "hot_clusters": clusters,
    })
    print(f"\n✅ screenshot_heat_scores.json: {out}")


def _write_review_queue(week: str, scores: dict, clusters: list, config: dict) -> None:
    candidate_th = config.get("candidate_threshold", DEFAULT_CANDIDATE_THRESHOLD)
    must_review_th = config.get("must_review_threshold", DEFAULT_MUST_REVIEW_THRESHOLD)

    ranked = sorted(scores.items(), key=lambda x: x[1]["total"], reverse=True)

    lines = [
        f"# {week} 高热截图复查清单",
        "",
        f"> 生成时间: {common.now_iso()}",
        f"> 候选阈值: {candidate_th} / 必审阈值: {must_review_th}",
        "",
    ]

    if clusters:
        lines += ["## 热点区间", ""]
        for i, cl in enumerate(clusters, 1):
            lines += [
                f"### Top {i}: {cl['range']}",
                f"- 截图数: {cl['count']}",
                f"- 平均热度: {cl['avg_score']}",
                f"- 最高热度: {cl['max_score']}",
                f"- 命中关键词: {', '.join(cl['keywords'])}",
                "",
                "**原因:**",
            ]
            reasons = []
            if cl["count"] > 1:
                reasons.append("连续多张截图有相关关键词")
            if any(scores[f].get("questions", 0) > 0 for f in cl["screenshots"]):
                reasons.append("出现多个问句")
            if any(scores[f].get("long_lines", 0) > 0 for f in cl["screenshots"]):
                reasons.append("出现长文本回复")
            if any(scores[f].get("response_hits") for f in cl["screenshots"]):
                reasons.append("出现回应词命中")
            for r in (reasons or ["热度分达标"]):
                lines.append(f"- {r}")

            level = "A（必审）" if cl["max_score"] >= must_review_th else "B（建议复查）"
            lines += [
                "",
                f"**建议:** 优先人工复查，可能形成 EVENT-{i:03d}。推荐级别: {level}",
                "",
            ]

    lines += ["## 所有截图热度排名", ""]
    lines += ["| 排名 | 截图 | 热度分 | 关键词 | 级别 |", "|------|------|--------|--------|------|"]
    for rank, (fname, s) in enumerate(ranked, 1):
        kw = ", ".join(s.get("keyword_hits", [])[:5])
        t = s["total"]
        if t >= must_review_th:
            level = "🔴 必审"
        elif t >= candidate_th:
            level = "🟡 候选"
        else:
            level = "⚪ 低"
        lines.append(f"| {rank} | {fname} | {t} | {kw} | {level} |")

    out = common.week_dir(week) / "review_queue.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ review_queue.md: {out}")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="IP 群高光 · 截图热度评分")
    p.add_argument("--week", required=True)
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    from phone_capture import load_yaml_config
    config = load_yaml_config()
    run_scoring(args.week, config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
