#!/usr/bin/env python3
"""IP 群高光 · Day 1 OCR 管线

读取 runs/{week}/screenshots/*.png，做 Tesseract OCR，
输出 ocr_text.md + ocr_health_report.md。
不调用任何云 OCR 或 LLM API。

用法：
    python src/ocr_pipeline.py --week 2026-W24
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import common

HIGHLIGHT_KEYWORDS = [
    "IP", "定位", "朋友圈", "成交", "流量", "内容", "复盘",
    "私域", "产品", "用户", "变现", "案例", "选题", "认知",
    "方法", "训练营", "小红书", "抖音", "账号",
]


def screenshots_dir(week: str) -> Path:
    return common.week_dir(week) / "screenshots"


def get_tesseract_fn(config: dict):
    """Try to load Tesseract. Returns (ocr_fn, engine_name) or (None, reason)."""
    ocr_cfg = config.get("ocr") or {}
    tess_cmd = ocr_cfg.get("tesseract_cmd")
    lang = ocr_cfg.get("lang", "chi_sim+eng")

    try:
        from PIL import Image
        import pytesseract
        if tess_cmd:
            pytesseract.pytesseract.tesseract_cmd = tess_cmd
        pytesseract.get_tesseract_version()

        def ocr_fn(img_path: Path) -> str:
            img = Image.open(img_path)
            return pytesseract.image_to_string(img, lang=lang)

        return ocr_fn, "Tesseract"
    except ImportError:
        return None, "pytesseract 或 Pillow 未安装。运行: pip install pytesseract Pillow"
    except Exception as e:
        return None, f"Tesseract 不可用: {e}"


def run_ocr(week: str, config: dict, force: bool = False) -> dict[str, str]:
    """OCR all screenshots. Returns {filename: text}."""
    sdir = screenshots_dir(week)
    if not sdir.exists():
        print(f"❌ 截图目录不存在: {sdir}")
        print(f"   请先运行: python src/phone_capture.py --week {week}")
        sys.exit(1)

    pngs = sorted(sdir.glob("*.png"))
    if not pngs:
        print(f"❌ 截图目录为空: {sdir}")
        sys.exit(1)

    ocr_fn, engine = get_tesseract_fn(config)

    if ocr_fn is None:
        print(f"⚠️  OCR 引擎不可用: {engine}")
        print("   将生成空模板，请手动填写 ocr_text.md")
        return _generate_placeholder(week, pngs, engine)

    print(f"🔤 OCR 引擎: {engine}")
    print(f"   截图数: {len(pngs)}")

    results: dict[str, str] = {}
    for png in pngs:
        fname = png.name
        try:
            text = ocr_fn(png).strip()
        except Exception as e:
            text = ""
            print(f"  ⚠️  {fname} OCR 失败: {e}")
        results[fname] = text
        chars = len(text)
        status = "✅" if chars > 20 else ("⚠️" if chars > 0 else "❌")
        print(f"  {status} {fname}: {chars} 字符")

    _write_ocr_text(week, results, engine)
    _write_health_report(week, results)

    return results


def _generate_placeholder(week: str, pngs: list[Path], reason: str) -> dict[str, str]:
    """Generate empty OCR results with template for manual fill."""
    results = {p.name: "" for p in pngs}
    _write_ocr_text(week, results, f"手动填写（{reason}）")
    _write_health_report(week, results)
    return results


def _write_ocr_text(week: str, results: dict[str, str], engine: str) -> None:
    lines = [
        f"# OCR 文本提取 · {week}",
        "",
        f"> 引擎: {engine}",
        f"> 截图数: {len(results)}",
        "",
    ]
    for fname in sorted(results.keys()):
        text = results[fname]
        lines.append(f"## {fname}")
        lines.append("```")
        lines.append(text if text else "（未识别到文本，请手动填写）")
        lines.append("```")
        lines.append("")

    out = common.week_dir(week) / "ocr_text.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✅ ocr_text.md: {out}")


def _write_health_report(week: str, results: dict[str, str]) -> None:
    total = len(results)
    char_counts = {f: len(t) for f, t in results.items()}
    failed = [f for f, c in char_counts.items() if c == 0]
    suspect_blank = [f for f, c in char_counts.items() if 0 < c <= 10]
    healthy = [f for f, c in char_counts.items() if c > 20]

    keyword_hits: dict[str, list[str]] = {}
    for fname, text in results.items():
        hits = [kw for kw in HIGHLIGHT_KEYWORDS if kw in text]
        if hits:
            keyword_hits[fname] = hits

    needs_review = sorted(set(failed + suspect_blank))

    lines = [
        f"# OCR 健康报告 · {week}",
        "",
        "## 总览",
        "",
        f"- 总截图数: {total}",
        f"- 识别成功（>20 字符）: {len(healthy)}",
        f"- 疑似空白（1-10 字符）: {len(suspect_blank)}",
        f"- 识别失败（0 字符）: {len(failed)}",
        "",
        "## 每张截图字符数",
        "",
        "| 截图 | 字符数 | 状态 |",
        "|------|--------|------|",
    ]
    for fname in sorted(char_counts.keys()):
        c = char_counts[fname]
        if c == 0:
            st = "❌ 失败"
        elif c <= 10:
            st = "⚠️ 疑似空白"
        elif c <= 50:
            st = "🟡 较少"
        else:
            st = "✅ 正常"
        lines.append(f"| {fname} | {c} | {st} |")

    lines += ["", "## 命中高光关键词", ""]
    if keyword_hits:
        for fname in sorted(keyword_hits.keys()):
            lines.append(f"- **{fname}**: {', '.join(keyword_hits[fname])}")
    else:
        lines.append("（无关键词命中）")

    lines += ["", "## 推荐人工复查的截图", ""]
    if needs_review:
        for f in needs_review:
            reason = "识别失败" if f in failed else "疑似空白"
            lines.append(f"- **{f}**: {reason}")
    else:
        lines.append("（无需人工复查）")

    out = common.week_dir(week) / "ocr_health_report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ ocr_health_report.md: {out}")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="IP 群高光 · OCR 管线")
    p.add_argument("--week", required=True)
    p.add_argument("--force", action="store_true")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    from phone_capture import load_yaml_config
    config = load_yaml_config()
    run_ocr(args.week, config, args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
