#!/usr/bin/env python3
"""IP 群高光 · OCR 文字提取

三种工作模式（自动选择，优先级从高到低）：

1. 本地 Tesseract（最准）
   pip install -r requirements.txt
   安装 Tesseract-OCR + chi_sim 语言包，见 tools/adb-setup.md

2. 手动 OCR 填写模板（无 Tesseract 时）
   首次运行会生成 runs/<week>/manual_ocr_template.md，
   你在里面按截图逐张填写聊天文字后，再运行 event_detector 即可。

3. 占位模式（两者都没有）
   生成带截图列表的 ocr_text.md，内容为空，供参考。

输出：
    runs/<week>/ocr_text.md      人工可读
    runs/<week>/ocr_cache.json   供 event_detector 使用的 {sha256: text} 缓存

用法：
    python src/ocr_extract.py --week 2026-W24
    python src/ocr_extract.py --week 2026-W24 --force   # 忽略缓存重新识别
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import common

# ──────────────────────────────────────────────
# 手动填写模板的格式标记
# ──────────────────────────────────────────────
_BEGIN = "<!-- OCR BEGIN -->"
_END   = "<!-- OCR END -->"


def parse_args(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--week", required=True)
    p.add_argument("--force", action="store_true", help="忽略缓存，全部重新识别")
    p.add_argument("--config", default=str(common.DEFAULT_CONFIG_PATH))
    p.add_argument(
        "--api-ocr",
        action="store_true",
        help="（未实现）允许调用外部 API 做 OCR。默认关闭，须显式传入才生效，"
             "以保证默认流程 0 API 消耗。",
    )
    return p.parse_args(argv)


# ──────────────────────────────────────────────
# OCR 引擎
# ──────────────────────────────────────────────

def get_ocr_fn(config: dict):
    """返回 (fn(path)->str, engine_desc)，或 (None, reason_str)。"""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return None, "pytesseract/Pillow 未安装（pip install -r requirements.txt）"

    ocr_cfg = (config.get("ocr") or {})
    tcmd = ocr_cfg.get("tesseract_cmd")
    if tcmd:
        pytesseract.pytesseract.tesseract_cmd = tcmd

    try:
        ver = pytesseract.get_tesseract_version()
    except Exception as e:
        return None, f"tesseract 本体未安装或路径不对（{e}）"

    lang = ocr_cfg.get("lang", "chi_sim+eng")

    def _run(path: Path) -> str:
        with Image.open(path) as img:
            return pytesseract.image_to_string(img, lang=lang)

    return _run, f"tesseract {ver} lang={lang}"


# ──────────────────────────────────────────────
# 手动填写模板：写入 & 解析
# ──────────────────────────────────────────────

def _manual_template_path(week: str) -> Path:
    return common.week_dir(week) / "manual_ocr_template.md"


def write_manual_template(week: str, manifest: dict, reason: str) -> Path:
    """生成让用户手动填写的 OCR 模板。"""
    path = _manual_template_path(week)
    if path.exists():
        return path  # 已存在，不覆盖（用户可能已经填写过）

    sections: list[str] = []
    for gid, gs in manifest.get("groups", {}).items():
        gname = gs.get("name", gid)
        for entry in gs.get("screens", []):
            sections.append(
                f"## {gname} · {entry['file'].split('/')[-1]}\n"
                f"> 文件：{entry['file']}\n\n"
                f"{_BEGIN}\n\n{_END}\n"
            )
        for date, bf in gs.get("backfills", {}).items():
            for entry in bf.get("screens", []):
                sections.append(
                    f"## {gname}（补采 {date}）· {entry['file'].split('/')[-1]}\n"
                    f"> 文件：{entry['file']}\n\n"
                    f"{_BEGIN}\n\n{_END}\n"
                )

    content = (
        f"# 手动 OCR 填写模板 · {week}\n\n"
        f"> OCR 引擎未就绪（{reason}）。\n"
        f"> 请在每个截图的 `{_BEGIN}` 和 `{_END}` 之间，\n"
        f"> 把该截图里看到的聊天文字抄写进来（每条消息一行）。\n"
        f"> 填写完毕后运行：python src/event_detector.py --week {week}\n\n"
        f"---\n\n"
        + "\n---\n\n".join(sections)
    )
    path.write_text(content, encoding="utf-8")
    return path


def load_manual_template(week: str, manifest: dict) -> dict[str, str]:
    """解析用户已填写的手动模板，返回 {sha256: text}。"""
    path = _manual_template_path(week)
    if not path.exists():
        return {}

    raw = path.read_text(encoding="utf-8")
    # 找所有 BEGIN...END 之间的文本
    blocks = re.findall(
        re.escape(_BEGIN) + r"\s*(.*?)\s*" + re.escape(_END),
        raw,
        flags=re.DOTALL,
    )

    # 建立 sha256 -> text 映射：按截图顺序对应 blocks
    sha_list: list[str] = []
    for gs in manifest.get("groups", {}).values():
        for entry in gs.get("screens", []):
            sha_list.append(entry["sha256"])
        for bf in gs.get("backfills", {}).values():
            for entry in bf.get("screens", []):
                sha_list.append(entry["sha256"])

    result = {}
    for sha, text in zip(sha_list, blocks):
        result[sha] = text.strip()
    return result


# ──────────────────────────────────────────────
# 迭代所有截图
# ──────────────────────────────────────────────

def iter_screenshots(manifest: dict):
    for gid, gs in manifest.get("groups", {}).items():
        label = f"{gs.get('name', gid)}（{gs.get('role', '')}）"
        for entry in gs.get("screens", []):
            yield gid, label, entry
        for date, bf in gs.get("backfills", {}).items():
            for entry in bf.get("screens", []):
                yield gid, f"{label} · 补采 {date}", entry


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────

def main(argv=None) -> int:
    args = parse_args(argv)

    if args.api_ocr:
        print("[安全提示] --api-ocr 已传入：如果本地 OCR 不可用，将尝试调用外部 API。")
        print("           当前版本：API OCR 未实现，将自动降级为手动模板模式。")

    config = common.load_config(Path(args.config))
    week = args.week

    manifest = common.load_manifest(week)
    all_shots = list(iter_screenshots(manifest))

    if not all_shots:
        print("[警告] manifest 里没有截图，请先运行 build_manifest.py。")
        # 写空的 ocr_text.md
        common.ocr_text_path(week).write_text(
            f"# OCR 文本提取 · {week}\n\n（没有截图）\n", encoding="utf-8"
        )
        return 0

    ocr_fn, engine_desc = get_ocr_fn(config)

    # 没有 OCR 引擎：先看现有缓存是否已覆盖全部截图
    if ocr_fn is None:
        existing_cache: dict = common.load_json(common.ocr_cache_path(week), default={})
        all_shas = {e["sha256"] for _, _, e in all_shots}
        if not args.force and all_shas and all_shas.issubset(existing_cache.keys()):
            print(f"[OCR] 缓存已覆盖全部 {len(all_shas)} 张截图，跳过 OCR 引擎")
            engine_desc = "缓存（已预填）"
            # fall through to ocr_text.md generation below
        else:
            manual_cache = load_manual_template(week, manifest)
            if manual_cache and any(v for v in manual_cache.values()):
                # 用户已填写模板
                print(f"[OCR] 使用手动填写模板（已填 {sum(1 for v in manual_cache.values() if v)} 张）")
                cache: dict = existing_cache
                cache.update(manual_cache)
                common.write_json(common.ocr_cache_path(week), cache)
                engine_desc = "手动填写"
            else:
                # 生成模板，输出占位
                tpl_path = write_manual_template(week, manifest, engine_desc)
                print(f"[OCR] 引擎未就绪：{engine_desc}", file=sys.stderr)
                print(f"  已生成手动填写模板：{tpl_path}", file=sys.stderr)
                print(f"  请在模板里填写聊天文字，然后运行：python src/event_detector.py --week {week}", file=sys.stderr)

                common.ocr_text_path(week).write_text(
                    f"# OCR 文本提取 · {week}\n\n"
                    f"> ⚠️ OCR 引擎未就绪（{engine_desc}）。\n"
                    f"> 请填写：{tpl_path}\n\n"
                    + "\n".join(f"- {e['file']}" for _, _, e in all_shots),
                    encoding="utf-8",
                )
                return 1  # 非 0 表示需要手动干预

    # 有 OCR 引擎（或手动模板已加载 / 缓存已覆盖）
    # 无引擎时（ocr_fn is None）忽略 --force，避免丢失手动填写的内容
    if ocr_fn is None:
        cache: dict = common.load_json(common.ocr_cache_path(week), default={})
    else:
        cache = {} if args.force else common.load_json(common.ocr_cache_path(week), default={})

    new_count = 0
    for _, _, entry in all_shots:
        sha = entry["sha256"]
        if sha in cache:
            continue
        if ocr_fn is None:
            # 手动模板未覆盖此截图：置空（不抛异常）
            cache[sha] = ""
            continue
        img = common.PROJECT_ROOT / entry["file"]
        if not img.exists():
            cache[sha] = ""
            continue
        try:
            cache[sha] = ocr_fn(img)
        except Exception as e:
            print(f"  ⚠️  OCR 失败 {entry['file']}: {e}", file=sys.stderr)
            cache[sha] = ""
        new_count += 1
        if new_count % 10 == 0:
            common.write_json(common.ocr_cache_path(week), cache)
            print(f"  ... 已识别 {new_count} 张")

    common.write_json(common.ocr_cache_path(week), cache)

    # 写 ocr_text.md
    lines = [f"# OCR 文本提取 · {week}", f"", f"> 引擎：{engine_desc}", ""]
    cur_gid = None
    for gid, label, entry in all_shots:
        if gid != cur_gid:
            lines += [f"## {label}", ""]
            cur_gid = gid
        text = (cache.get(entry["sha256"]) or "").strip()
        lines += [f"### {entry['file'].split('/')[-1]}", "```", text or "（空）", "```", ""]

    common.ocr_text_path(week).write_text("\n".join(lines), encoding="utf-8")

    total = len(all_shots)
    print(f"✅ OCR 完成：{total} 张，新处理 {new_count} 张 -> {common.ocr_text_path(week)}")
    print(f"   下一步：python src/event_detector.py --week {week}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
