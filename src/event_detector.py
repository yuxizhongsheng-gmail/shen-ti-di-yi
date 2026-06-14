#!/usr/bin/env python3
"""IP 群高光 · 规则化高响应事件检测

读取 ocr_text（通过 ocr_cache.json + capture_manifest.json 重建按截图顺序排列的文本行），
用纯关键词/规则匹配筛出三类候选高光事件，不调用任何大模型 API。

三类事件：
    1. member_work_feedback        群友作品引发反馈
    2. topic_discussion            群友话题引发讨论
    3. muted_group_owner_response  禁言群群主内容在交流群引发响应

输出：
    runs/<week>/candidate_events.md   人工/Claude 快速浏览用
    runs/<week>/event_scores.json     结构化数据，供下一步筛选使用

这一步产出的是「候选」，不是结论 —— 真正的判断（是否真的有价值、怎么改写）
留给 prompts/01-extract.md 配合 Claude/GPT 来做。

用法：
    python src/event_detector.py --week 2026-W24
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import common

TYPE_LABELS = {
    "member_work_feedback": "群友作品引发反馈",
    "topic_discussion": "群友话题引发讨论",
    "muted_group_owner_response": "禁言群群主内容在交流群引发响应",
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="规则化高响应事件检测（不调用大模型）")
    parser.add_argument("--week", required=True, help="周数，如 2026-W24")
    parser.add_argument("--config", default=str(common.DEFAULT_CONFIG_PATH), help="配置文件路径")
    parser.add_argument("--rules", default=str(common.DEFAULT_RULES_PATH), help="事件规则文件路径")
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# 构建按截图顺序排列的文本行
# ---------------------------------------------------------------------------

def build_line_streams(manifest: dict, cache: dict) -> dict[str, list[dict]]:
    """返回 {group_id: [{"text", "file", "scope"}, ...]}，按采集顺序排列。

    同一 group_id 下，main 与各 backfill 的行按 (scope 名称) 顺序依次拼接——
    backfill 视为同一群的延伸文本，供跨群规则统一检索。
    """
    streams: dict[str, list[dict]] = {}
    for group_id, group_state in manifest.get("groups", {}).items():
        lines: list[dict] = []
        for entry in group_state.get("screens", []):
            text = cache.get(entry["sha256"], "")
            for raw in text.splitlines():
                t = raw.strip()
                if t:
                    lines.append({"text": t, "file": entry["file"], "scope": "main"})
        for date, backfill_state in sorted(group_state.get("backfills", {}).items()):
            for entry in backfill_state.get("screens", []):
                text = cache.get(entry["sha256"], "")
                for raw in text.splitlines():
                    t = raw.strip()
                    if t:
                        lines.append({"text": t, "file": entry["file"], "scope": f"backfill_{date}"})
        streams[group_id] = lines
    return streams


def merge_into_blocks(lines: list[dict]) -> list[list[dict]]:
    """把连续的"正文行"合并为段落块；遇到很短的行（疑似时间/昵称/表情回应）就断开。"""
    blocks: list[list[dict]] = []
    current: list[dict] = []
    for item in lines:
        if len(item["text"]) <= 3:
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(item)
    if current:
        blocks.append(current)
    return blocks


def char_ngrams(text: str, n: int = 4) -> set[str]:
    text = "".join(text.split())
    if len(text) < n:
        return {text} if text else set()
    return {text[i:i + n] for i in range(len(text) - n + 1)}


# ---------------------------------------------------------------------------
# 规则 1 & 2：单群内的逐行扫描
# ---------------------------------------------------------------------------

def detect_in_group_events(
    group_id: str,
    label: str,
    lines: list[dict],
    rules: dict,
) -> list[dict]:
    events = []
    reaction_kw = rules.get("reaction_keywords", [])
    share_kw = rules.get("share_keywords", [])
    question_kw = rules.get("question_indicators", [])
    window = rules.get("response_window_lines", 8)
    min_work = rules.get("min_responses_for_work_feedback", 2)
    min_disc = rules.get("min_responses_for_discussion", 3)
    weights = rules.get("score_weights", {})
    base_w = weights.get("base_response", 1.0)
    kw_w = weights.get("keyword_match", 0.5)

    for i, item in enumerate(lines):
        text = item["text"]

        # 规则 1：群友作品引发反馈
        share_hits = [kw for kw in share_kw if kw in text]
        if share_hits:
            responses = []
            for j in range(i + 1, min(i + 1 + window, len(lines))):
                if any(kw in lines[j]["text"] for kw in reaction_kw):
                    responses.append(lines[j])
            if len(responses) >= min_work:
                events.append({
                    "type": "member_work_feedback",
                    "group": group_id,
                    "label": label,
                    "trigger_line": text,
                    "response_lines": [r["text"] for r in responses],
                    "keywords_matched": share_hits,
                    "source_screens": _unique_files([item] + responses),
                    "score": round(base_w * len(responses) + kw_w * len(share_hits), 2),
                })

        # 规则 2：群友话题引发讨论
        is_question = text.rstrip().endswith(("?", "？")) or any(kw in text for kw in question_kw)
        if is_question:
            responses = []
            for j in range(i + 1, min(i + 1 + window, len(lines))):
                cand = lines[j]["text"]
                if len(cand) >= 4 and not any(kw in cand for kw in reaction_kw):
                    responses.append(lines[j])
            if len(responses) >= min_disc:
                events.append({
                    "type": "topic_discussion",
                    "group": group_id,
                    "label": label,
                    "trigger_line": text,
                    "response_lines": [r["text"] for r in responses],
                    "keywords_matched": [kw for kw in question_kw if kw in text],
                    "source_screens": _unique_files([item] + responses),
                    "score": round(base_w * len(responses), 2),
                })

    return events


def _unique_files(items: list[dict]) -> list[str]:
    seen = []
    for it in items:
        if it["file"] not in seen:
            seen.append(it["file"])
    return seen


# ---------------------------------------------------------------------------
# 规则 3：跨群（禁言群群主内容 -> 交流群响应）
# ---------------------------------------------------------------------------

def detect_cross_group_events(
    trigger_group_id: str,
    trigger_label: str,
    trigger_lines: list[dict],
    main_group_id: str,
    main_label: str,
    main_lines: list[dict],
    rules: dict,
) -> list[dict]:
    events = []
    min_len = rules.get("min_announcement_length", 20)
    overlap_threshold = rules.get("cross_group_keyword_overlap", 2)
    reaction_kw = rules.get("reaction_keywords", [])
    weights = rules.get("score_weights", {})
    base_w = weights.get("base_response", 1.0)
    cross_bonus = weights.get("cross_group_bonus", 2.0)

    blocks = merge_into_blocks(trigger_lines)
    main_grams = [(item, char_ngrams(item["text"])) for item in main_lines]

    for block in blocks:
        block_text = "".join(item["text"] for item in block)
        if len(block_text) < min_len:
            continue
        block_grams = char_ngrams(block_text)
        if not block_grams:
            continue

        matches = []
        for item, grams in main_grams:
            overlap = len(block_grams & grams)
            if overlap >= overlap_threshold:
                matches.append(item)

        if not matches:
            continue

        # 在匹配位置附近统计反应类回复，作为"响应强度"
        match_indices = {id(m) for m in matches}
        response_count = 0
        for idx, item in enumerate(main_lines):
            if id(item) in match_indices:
                for j in range(idx + 1, min(idx + 4, len(main_lines))):
                    if any(kw in main_lines[j]["text"] for kw in reaction_kw):
                        response_count += 1

        events.append({
            "type": "muted_group_owner_response",
            "group": main_group_id,
            "label": f"{trigger_label} -> {main_label}",
            "trigger_line": block_text[:200],
            "response_lines": [m["text"] for m in matches][:10],
            "keywords_matched": [],
            "source_screens": _unique_files(block + matches),
            "score": round(base_w * (len(matches) + response_count) + cross_bonus, 2),
        })

    return events


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def write_outputs(week: str, events: list[dict]) -> None:
    by_type: dict[str, list[dict]] = {}
    for e in events:
        by_type.setdefault(e["type"], []).append(e)
    for evs in by_type.values():
        evs.sort(key=lambda e: e["score"], reverse=True)

    # event_scores.json
    scored = []
    for type_key, evs in by_type.items():
        for i, e in enumerate(evs, start=1):
            e_with_id = {"id": f"{e['group']}-{type_key}-{i:03d}", **e}
            scored.append(e_with_id)

    summary = {
        "total_candidates": len(scored),
        "by_type": {k: len(v) for k, v in by_type.items()},
    }
    common.write_json(common.event_scores_path(week), {
        "week": week,
        "generated_at": common.now_iso(),
        "summary": summary,
        "events": scored,
    })

    # candidate_events.md
    lines = [
        f"# 候选高光事件 · {week}",
        "",
        "> 以下为规则筛选结果，不是最终结论。下一步：把本文件和 inbox 素材一起交给 "
        "Claude/GPT，按 `prompts/01-extract.md` 做 A/B/C 精筛。",
        "",
        f"共 {summary['total_candidates']} 条候选："
        + " / ".join(f"{TYPE_LABELS.get(k, k)} {v}" for k, v in summary["by_type"].items()),
        "",
    ]

    for type_key, label in TYPE_LABELS.items():
        evs = by_type.get(type_key, [])
        lines.append(f"## {label}（{len(evs)}）")
        lines.append("")
        if not evs:
            lines.append("（本周无候选）")
            lines.append("")
            continue
        for i, e in enumerate(evs, start=1):
            lines.append(f"### [{e['group']}-{type_key}-{i:03d}] 分数 {e['score']} · {e['label']}")
            lines.append(f"- 触发内容：「{e['trigger_line']}」")
            if e["response_lines"]:
                lines.append(f"- 后续/响应（{len(e['response_lines'])} 条）：")
                for r in e["response_lines"]:
                    lines.append(f"  - 「{r}」")
            if e["keywords_matched"]:
                lines.append(f"- 命中关键词：{', '.join(e['keywords_matched'])}")
            lines.append(f"- 截图来源：{', '.join(e['source_screens'])}")
            lines.append("")

    common.candidate_events_path(week).write_text("\n".join(lines), encoding="utf-8")


def main(argv=None) -> int:
    args = parse_args(argv)
    config = common.load_config(Path(args.config))
    rules = common.load_rules(Path(args.rules))
    week = args.week

    manifest = common.load_manifest(week)
    if not manifest.get("groups"):
        print(f"[错误] {common.manifest_path(week)} 里没有任何分组/截图记录，请先运行 wechat_capture_bot.py 和 ocr_extract.py。", file=sys.stderr)
        return 1

    cache = common.load_json(common.ocr_cache_path(week), default={})
    if not cache:
        print(f"[错误] {common.ocr_cache_path(week)} 为空，请先运行 ocr_extract.py。", file=sys.stderr)
        return 1

    streams = build_line_streams(manifest, cache)

    group_meta = {g["id"]: g for g in config.get("groups", [])}
    events: list[dict] = []

    for group_id, lines in streams.items():
        meta = group_meta.get(group_id, {})
        label = f"{meta.get('name', group_id)}（{meta.get('role', '')}）"
        events += detect_in_group_events(group_id, label, lines, rules)

    # 跨群规则：muted 群 -> 非 muted 群
    muted_groups = [g for g in config.get("groups", []) if g.get("muted")]
    main_groups = [g for g in config.get("groups", []) if not g.get("muted")]
    for trigger_g in muted_groups:
        for main_g in main_groups:
            t_id, m_id = trigger_g["id"], main_g["id"]
            if t_id not in streams or m_id not in streams:
                continue
            events += detect_cross_group_events(
                t_id, f"{trigger_g['name']}（{trigger_g.get('role','')}）", streams[t_id],
                m_id, f"{main_g['name']}（{main_g.get('role','')}）", streams[m_id],
                rules,
            )

    write_outputs(week, events)

    print(f"完成：共发现 {len(events)} 条候选高光事件。")
    print(f"输出：{common.candidate_events_path(week)}")
    print(f"输出：{common.event_scores_path(week)}")
    print("下一步：把 candidate_events.md 和本周 inbox 素材一起交给 Claude/GPT，用 prompts/01-extract.md 精筛。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
