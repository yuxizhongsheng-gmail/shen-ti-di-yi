#!/usr/bin/env python3
"""IP 群高光 · 一键生成全套周刊（调用 DeepSeek 或 Claude API）

用法：
    # 使用 DeepSeek（默认，便宜）
    python scripts/generate_digest.py --week 2026-W24

    # 使用 Claude
    python scripts/generate_digest.py --week 2026-W24 --provider claude

    # 跳过某些步骤
    python scripts/generate_digest.py --week 2026-W24 --skip 03,04

需要环境变量：
    DEEPSEEK_API_KEY  (使用 DeepSeek 时)
    ANTHROPIC_API_KEY  (使用 Claude 时)

输出：
    runs/<week>/01-extract.md          精华筛选
    outputs/<week>-full.md             正式周刊
    outputs/<week>-wechat-short.md     微信群短版
    outputs/<week>-feishu.md           飞书文档版
    knowledge/<week>-archive.md        知识沉淀
    runs/<week>/06-next-week-plan.md   下周运营计划
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import common


STEPS = {
    "01": {
        "name": "精华筛选",
        "prompt_file": "prompts/01-extract.md",
        "output": "runs/{week}/01-extract.md",
        "inputs": ["runs/{week}/candidate_events.md", "runs/{week}/ocr_text.md"],
    },
    "02": {
        "name": "正式周刊",
        "prompt_file": "prompts/02-weekly-digest.md",
        "output": "outputs/{week}-full.md",
        "inputs": ["runs/{week}/01-extract.md", "runs/{week}/ocr_text.md"],
    },
    "03": {
        "name": "微信群短版",
        "prompt_file": "prompts/03-wechat-short.md",
        "output": "outputs/{week}-wechat-short.md",
        "inputs": ["outputs/{week}-full.md"],
    },
    "04": {
        "name": "飞书文档版",
        "prompt_file": "prompts/04-feishu-version.md",
        "output": "outputs/{week}-feishu.md",
        "inputs": ["outputs/{week}-full.md"],
    },
    "05": {
        "name": "知识沉淀",
        "prompt_file": "prompts/05-archive-knowledge.md",
        "output": "knowledge/{week}-archive.md",
        "inputs": ["runs/{week}/01-extract.md", "outputs/{week}-full.md"],
    },
    "06": {
        "name": "下周运营计划",
        "prompt_file": "prompts/06-next-week-plan.md",
        "output": "runs/{week}/06-next-week-plan.md",
        "inputs": ["outputs/{week}-full.md"],
    },
}


def call_deepseek(system_prompt: str, user_content: str) -> str:
    import urllib.request

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY 环境变量未设置")

    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.7,
        "max_tokens": 4096,
    }).encode()

    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def call_claude(system_prompt: str, user_content: str) -> str:
    import urllib.request

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY 环境变量未设置")

    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_content},
        ],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["content"][0]["text"]


def run_step(step_id: str, week: str, provider: str) -> None:
    step = STEPS[step_id]
    prompt_path = ROOT / step["prompt_file"]
    output_path = ROOT / step["output"].format(week=week)

    print(f"\n{'='*60}")
    print(f"  步骤 {step_id}: {step['name']}")
    print(f"{'='*60}")

    system_prompt = prompt_path.read_text(encoding="utf-8")

    input_parts = []
    for inp in step["inputs"]:
        p = ROOT / inp.format(week=week)
        if not p.exists():
            print(f"  ⚠️  输入文件不存在，跳过: {p}")
            return
        input_parts.append(f"--- {p.name} ---\n{p.read_text(encoding='utf-8')}")

    user_content = "\n\n".join(input_parts)

    print(f"  调用 {provider} API ...")
    if provider == "deepseek":
        result = call_deepseek(system_prompt, user_content)
    else:
        result = call_claude(system_prompt, user_content)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result, encoding="utf-8")
    print(f"  ✅ 输出: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="一键生成全套周刊")
    parser.add_argument("--week", required=True, help="周编号，如 2026-W24")
    parser.add_argument("--provider", choices=["deepseek", "claude"], default="deepseek")
    parser.add_argument("--skip", default="", help="跳过的步骤编号，逗号分隔，如 03,04")
    parser.add_argument("--only", default="", help="只跑指定步骤，逗号分隔，如 01,02")
    args = parser.parse_args()

    candidates = ROOT / f"runs/{args.week}/candidate_events.md"
    if not candidates.exists():
        print(f"❌ 未找到候选文件: {candidates}")
        print(f"   请先运行: python src/event_detector.py --week {args.week}")
        return 1

    skip = set(args.skip.split(",")) if args.skip else set()
    only = set(args.only.split(",")) if args.only else set()

    for step_id in STEPS:
        if only and step_id not in only:
            continue
        if step_id in skip:
            print(f"\n  ⏭️  跳过步骤 {step_id}: {STEPS[step_id]['name']}")
            continue
        run_step(step_id, args.week, args.provider)

    print(f"\n{'='*60}")
    print(f"  🎉 全部完成！")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
