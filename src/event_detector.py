#!/usr/bin/env python3
"""IP 群高光 · 规则化事件检测

读取 ocr_cache.json + capture_manifest.json，
用纯关键词/规则筛出三类候选高光事件，不调用大模型。

三类事件：
    1. member_work_feedback        群友作品引发反馈
    2. topic_discussion            群友话题引发多人讨论
    3. muted_group_owner_response  禁言群群主信息在交流群引发响应

每条事件的评分维度：
    • 多人响应 (0-2)      ─ response_count >= 2 → 满分
    • 有触发点 (0-2)      ─ 命中 share/question 关键词
    • 反馈质量 (0-1.5)    ─ 反馈关键词命中数量
    • 适合公开 (0/1)      ─ 无隐私红旗词为满分，有则扣分并标记
    [跨群加成 +2]

输出：
    runs/<week>/candidate_events.md    人工速览 + 下一步给 Claude
    runs/<week>/event_scores.json      结构化数据

用法：
    python src/event_detector.py --week 2026-W24
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import common

TYPE_CN = {
    "member_work_feedback":       "群友作品引发反馈",
    "topic_discussion":           "群友话题引发多人讨论",
    "muted_group_owner_response": "禁言群群主信息在交流群引发响应",
}


def parse_args(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--week", required=True)
    p.add_argument("--config", default=str(common.DEFAULT_CONFIG_PATH))
    p.add_argument("--rules", default=str(common.DEFAULT_RULES_PATH))
    return p.parse_args(argv)


# ─────────────────────────────────────────────
# 文本行流
# ─────────────────────────────────────────────

def build_streams(manifest: dict, cache: dict) -> dict[str, list[dict]]:
    """返回 {group_id: [{"text", "file"}, ...]} 按截图顺序。"""
    streams: dict[str, list[dict]] = {}
    for gid, gs in manifest.get("groups", {}).items():
        lines: list[dict] = []
        for entry in gs.get("screens", []):
            for raw in (cache.get(entry["sha256"]) or "").splitlines():
                t = raw.strip()
                if t:
                    lines.append({"text": t, "file": entry["file"]})
        for bf in gs.get("backfills", {}).values():
            for entry in bf.get("screens", []):
                for raw in (cache.get(entry["sha256"]) or "").splitlines():
                    t = raw.strip()
                    if t:
                        lines.append({"text": t, "file": entry["file"]})
        streams[gid] = lines
    return streams


# ─────────────────────────────────────────────
# 评分
# ─────────────────────────────────────────────

def score_event(response_items: list[dict], kw_hits: list[str],
                rules: dict, is_cross: bool = False) -> tuple[float, dict]:
    w = rules.get("score_weights", {})
    breakdown: dict[str, float] = {}

    # 1. 多人响应
    rc = len(response_items)
    breakdown["多人响应"] = round(min(rc / 2, 1.0) * w.get("multi_person_response", 2.0), 2)

    # 2. 有触发点
    breakdown["有触发点"] = round(min(len(kw_hits), 2) / 2 * w.get("has_trigger", 2.0), 2)

    # 3. 反馈质量（去重命中数）
    reaction_kw = rules.get("reaction_keywords", [])
    rq_hits = {r for item in response_items for r in reaction_kw if r in item["text"]}
    breakdown["反馈质量"] = round(min(len(rq_hits) / 3, 1.0) * w.get("reaction_quality", 1.5), 2)

    # 4. 适合公开（默认满分，有红旗词置 0）
    breakdown["适合公开"] = w.get("public_suitable", 1.0)

    if is_cross:
        breakdown["跨群加成"] = w.get("cross_group_bonus", 2.0)

    total = round(sum(breakdown.values()), 2)
    return total, breakdown


def is_not_public(texts: list[str], rules: dict) -> list[str]:
    """返回匹配到的隐私红旗词列表，空表示适合公开。"""
    red_flags = rules.get("not_public_keywords", [])
    hits = []
    for t in texts:
        for kw in red_flags:
            if kw in t and kw not in hits:
                hits.append(kw)
    return hits


def unique_files(items: list[dict]) -> list[str]:
    seen: list[str] = []
    for it in items:
        if it["file"] not in seen:
            seen.append(it["file"])
    return seen


# ─────────────────────────────────────────────
# 噪音行过滤
# ─────────────────────────────────────────────

import re as _re

_NOISE_PATTERNS = [
    _re.compile(r"^[上下]午?\s*\d{1,2}:\d{2}$"),
    _re.compile(r"^早\s*\d{1,2}:\d{2}$"),
    _re.compile(r"^周[一二三四五六日]\s*(早|上午|下午|晚)?\s*\d{1,2}:\d{2}$"),
    _re.compile(r"^\d{1,2}:\d{2}$"),
    _re.compile(r"^\d{4}年\d{1,2}月\d{1,2}日"),
    _re.compile(r"^[\U0001f300-\U0001f9ff].*训练营.*群$"),
    _re.compile(r"^【.*】.*群$"),
]


def is_noise_line(text: str) -> bool:
    t = text.strip()
    if len(t) <= 3:
        return True
    return any(p.match(t) for p in _NOISE_PATTERNS)


# ─────────────────────────────────────────────
# 去重：同一段对话只保留最高分候选
# ─────────────────────────────────────────────

def _response_overlap(a: list[str], b: list[str]) -> float:
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    inter = len(sa & sb)
    return inter / min(len(sa), len(sb))


def deduplicate_events(events: list[dict], overlap_threshold: float = 0.5) -> list[dict]:
    if not events:
        return events
    events.sort(key=lambda e: e["score"], reverse=True)
    kept: list[dict] = []
    for e in events:
        is_dup = False
        for k in kept:
            if e["type"] != k["type"]:
                continue
            if _response_overlap(e["response_lines"], k["response_lines"]) >= overlap_threshold:
                is_dup = True
                break
        if not is_dup:
            kept.append(e)
    return kept


# ─────────────────────────────────────────────
# 规则 1 & 2：单群内扫描
# ─────────────────────────────────────────────

def detect_single_group(gid: str, label: str,
                         lines: list[dict], rules: dict) -> list[dict]:
    events: list[dict] = []
    share_kw   = rules.get("share_keywords", [])
    question_kw = rules.get("question_indicators", [])
    reaction_kw = rules.get("reaction_keywords", [])
    window = rules.get("response_window_lines", 10)
    min_work = rules.get("min_responses_for_work_feedback", 2)
    min_disc = rules.get("min_responses_for_discussion", 3)

    for i, item in enumerate(lines):
        text = item["text"]

        if is_noise_line(text):
            continue

        # ─ 规则 1：群友作品 ─
        sh_hits = [k for k in share_kw if k in text]
        if sh_hits:
            resp = [lines[j] for j in range(i + 1, min(i + 1 + window, len(lines)))
                    if not is_noise_line(lines[j]["text"])
                    and any(k in lines[j]["text"] for k in reaction_kw)]
            if len(resp) >= min_work:
                all_texts = [text] + [r["text"] for r in resp]
                red = is_not_public(all_texts, rules)
                score, breakdown = score_event(resp, sh_hits, rules)
                if red:
                    breakdown["适合公开"] = 0
                    score = round(score - rules.get("score_weights", {}).get("public_suitable", 1.0), 2)
                events.append({
                    "type": "member_work_feedback",
                    "group": gid, "label": label,
                    "trigger_line": text,
                    "response_lines": [r["text"] for r in resp],
                    "keywords_matched": sh_hits,
                    "source_screens": unique_files([item] + resp),
                    "score": max(score, 0),
                    "score_breakdown": breakdown,
                    "not_public_flags": red,
                    "public_suitable": not bool(red),
                })

        # ─ 规则 2：群友话题 ─
        q_hits = [k for k in question_kw if k in text] + (
            ["？结尾"] if text.rstrip().endswith(("?", "？")) else []
        )
        if q_hits:
            resp = [lines[j] for j in range(i + 1, min(i + 1 + window, len(lines)))
                    if not is_noise_line(lines[j]["text"])
                    and len(lines[j]["text"]) >= 4
                    and not all(k in lines[j]["text"] for k in reaction_kw)]
            if len(resp) >= min_disc:
                all_texts = [text] + [r["text"] for r in resp]
                red = is_not_public(all_texts, rules)
                score, breakdown = score_event(resp, q_hits, rules)
                if red:
                    breakdown["适合公开"] = 0
                    score = round(score - rules.get("score_weights", {}).get("public_suitable", 1.0), 2)
                events.append({
                    "type": "topic_discussion",
                    "group": gid, "label": label,
                    "trigger_line": text,
                    "response_lines": [r["text"] for r in resp],
                    "keywords_matched": q_hits,
                    "source_screens": unique_files([item] + resp),
                    "score": max(score, 0),
                    "score_breakdown": breakdown,
                    "not_public_flags": red,
                    "public_suitable": not bool(red),
                })

    return events


# ─────────────────────────────────────────────
# 规则 3：跨群（禁言群 -> 交流群）
# ─────────────────────────────────────────────

def char_ngrams(text: str, n: int = 4) -> set[str]:
    t = "".join(text.split())
    return {t[i:i + n] for i in range(len(t) - n + 1)} if len(t) >= n else ({t} if t else set())


def merge_blocks(lines: list[dict]) -> list[list[dict]]:
    blocks: list[list[dict]] = []
    cur: list[dict] = []
    for item in lines:
        if len(item["text"]) <= 3:
            if cur:
                blocks.append(cur)
                cur = []
            continue
        cur.append(item)
    if cur:
        blocks.append(cur)
    return blocks


def detect_cross_group(
    trig_id: str, trig_label: str, trig_lines: list[dict],
    main_id: str, main_label: str, main_lines: list[dict],
    rules: dict,
) -> list[dict]:
    events: list[dict] = []
    min_len   = rules.get("min_announcement_length", 20)
    min_ol    = rules.get("cross_group_keyword_overlap", 2)
    reaction_kw = rules.get("reaction_keywords", [])

    main_grams = [(item, char_ngrams(item["text"])) for item in main_lines]

    for block in merge_blocks(trig_lines):
        block_text = "".join(it["text"] for it in block)
        if len(block_text) < min_len:
            continue
        bg = char_ngrams(block_text)
        if not bg:
            continue

        matches = [item for item, mg in main_grams if len(bg & mg) >= min_ol]
        if not matches:
            continue

        rc = sum(
            1 for idx, item in enumerate(main_lines)
            if id(item) in {id(m) for m in matches}
            for j in range(idx + 1, min(idx + 4, len(main_lines)))
            if any(k in main_lines[j]["text"] for k in reaction_kw)
        )

        all_texts = [it["text"] for it in block] + [m["text"] for m in matches]
        red = is_not_public(all_texts, rules)
        score, breakdown = score_event(matches, [], rules, is_cross=True)
        if red:
            breakdown["适合公开"] = 0
            score = round(score - rules.get("score_weights", {}).get("public_suitable", 1.0), 2)

        events.append({
            "type": "muted_group_owner_response",
            "group": main_id,
            "label": f"{trig_label} → {main_label}",
            "trigger_line": block_text[:300],
            "response_lines": [m["text"] for m in matches][:8],
            "keywords_matched": [],
            "source_screens": unique_files(block + matches),
            "score": max(score, 0),
            "score_breakdown": breakdown,
            "not_public_flags": red,
            "public_suitable": not bool(red),
        })

    return events


# ─────────────────────────────────────────────
# 输出
# ─────────────────────────────────────────────

def write_outputs(week: str, events: list[dict]) -> None:
    by_type: dict[str, list[dict]] = {}
    for e in events:
        by_type.setdefault(e["type"], []).append(e)
    for ev_list in by_type.values():
        ev_list.sort(key=lambda x: x["score"], reverse=True)

    # ── event_scores.json ──
    scored = []
    for tkey, ev_list in by_type.items():
        for i, e in enumerate(ev_list, 1):
            scored.append({"id": f"{e['group']}-{tkey}-{i:03d}", **e})

    common.write_json(common.event_scores_path(week), {
        "week": week,
        "generated_at": common.now_iso(),
        "summary": {
            "total": len(scored),
            "by_type": {k: len(v) for k, v in by_type.items()},
        },
        "events": scored,
    })

    # ── candidate_events.md ──
    total = len(scored)
    lines = [
        f"# 候选高光事件 · {week}",
        "",
        "> 以下由规则筛选自动生成，不是最终结论。",
        "> **下一步**：把本文件交给 Claude，配合 `prompts/01-extract.md` 做 A/B/C 精筛。",
        "",
        f"共 **{total}** 条候选：" +
        " / ".join(f"{TYPE_CN.get(k, k)} {len(v)}" for k, v in by_type.items()),
        "",
        "---",
        "",
    ]

    for tkey, cn_label in TYPE_CN.items():
        ev_list = by_type.get(tkey, [])
        lines += [f"## {cn_label}（{len(ev_list)} 条）", ""]
        if not ev_list:
            lines += ["（本周无候选）", ""]
            continue

        for i, e in enumerate(ev_list, 1):
            eid = f"{e['group']}-{tkey}-{i:03d}"
            pub_tag = "✅ 适合公开" if e.get("public_suitable", True) else f"⚠️ 不建议公开（{', '.join(e.get('not_public_flags', []))}）"
            bd_str = " | ".join(f"{k} {v}" for k, v in e.get("score_breakdown", {}).items())

            lines += [
                f"### [{eid}] 总分 {e['score']:.1f}",
                f"- **类型**：{TYPE_CN.get(tkey, tkey)}",
                f"- **群组**：{e['label']}",
                f"- **触发内容**：「{e['trigger_line'][:120]}」",
            ]
            if e["response_lines"]:
                lines.append(f"- **后续响应**（{len(e['response_lines'])} 条）：")
                for r in e["response_lines"][:5]:
                    lines.append(f"  - 「{r[:80]}」")
            if e.get("keywords_matched"):
                lines.append(f"- **命中关键词**：{', '.join(e['keywords_matched'])}")
            lines += [
                f"- **评分明细**：{bd_str}",
                f"- **适合公开**：{pub_tag}",
                f"- **截图来源**：{', '.join(e['source_screens'][:4])}",
                "",
            ]

    lines += [
        "---",
        "",
        "## 下一步",
        "",
        "把本文件 + 本周 `inbox/` 素材一起发给 Claude，",
        "用 `prompts/01-extract.md` 做 A/B/C 精筛，",
        "再依次跑 02~06 生成周刊/短版/知识沉淀/下周计划。",
    ]

    common.candidate_events_path(week).write_text("\n".join(lines), encoding="utf-8")


# ─────────────────────────────────────────────
# main
# ─────────────────────────────────────────────

def main(argv=None) -> int:
    args = parse_args(argv)
    config = common.load_config(Path(args.config))
    rules  = common.load_rules(Path(args.rules))
    week   = args.week

    manifest = common.load_manifest(week)
    cache    = common.load_json(common.ocr_cache_path(week), default={})

    if not cache:
        print("[警告] ocr_cache.json 为空，所有截图文字为空，候选事件可能为 0。")
        print("  先运行：python src/ocr_extract.py --week", week)

    streams   = build_streams(manifest, cache)
    group_meta = {g["id"]: g for g in config.get("groups", [])}
    events: list[dict] = []

    # 单群规则
    for gid, lines in streams.items():
        meta  = group_meta.get(gid, {})
        label = f"{meta.get('name', gid)}（{meta.get('role', '')}）"
        events += detect_single_group(gid, label, lines, rules)

    # 跨群规则
    muted = [g for g in config.get("groups", []) if g.get("muted")]
    mains = [g for g in config.get("groups", []) if not g.get("muted")]
    for tg in muted:
        for mg in mains:
            tid, mid = tg["id"], mg["id"]
            if tid not in streams or mid not in streams:
                continue
            events += detect_cross_group(
                tid, f"{tg['name']}（{tg.get('role', '')}）", streams[tid],
                mid, f"{mg['name']}（{mg.get('role', '')}）", streams[mid],
                rules,
            )

    raw_count = len(events)
    events = deduplicate_events(events)
    if raw_count != len(events):
        print(f"  去重：{raw_count} → {len(events)} 条（合并了重叠对话窗口）")

    write_outputs(week, events)

    print(f"✅ 规则检测完成：{len(events)} 条候选高光")
    print(f"   candidate_events.md -> {common.candidate_events_path(week)}")
    print(f"   event_scores.json   -> {common.event_scores_path(week)}")
    if events:
        print(f"\n下一步：把 candidate_events.md 交给 Claude，用 prompts/01-extract.md 精筛。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
