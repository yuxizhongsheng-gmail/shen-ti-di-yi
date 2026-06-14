#!/usr/bin/env python3
"""IP 群高光 · 本地 OCR 提取

读取 capture_manifest.json 里记录的截图，跑本地 OCR，输出 ocr_text.md。
不调用任何大模型 API —— OCR 是纯本地图像识别，不是「理解」，模型额度不应该花在这里。

依赖（本地安装，一次性）：
    pip install -r requirements.txt   # Pillow + pytesseract
    再安装 Tesseract-OCR 本体（Windows 安装器自带中文语言包勾选项）：
    https://github.com/UB-Mannheim/tesseract/wiki

如果依赖未安装，本脚本会在 ocr_text.md 里写入清晰的占位说明，并以非 0 退出码返回，
不会假装"完成"。

用法：
    python src/ocr_extract.py --week 2026-W24
    python src/ocr_extract.py --week 2026-W24 --force   # 忽略缓存，全部重新 OCR
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import common

PLACEHOLDER_TEMPLATE = """# OCR 文本提取 · {week}

> ⚠️ 本地 OCR 引擎未就绪，以下为占位说明，未执行任何识别。

## 问题

{reason}

## 如何修复

1. 安装 Python 依赖：
   ```
   pip install -r requirements.txt
   ```
   （即 Pillow + pytesseract）

2. 安装 Tesseract-OCR 本体（pytesseract 只是调用它的 Python 接口，本体需要单独装）：
   - Windows: 下载并安装 https://github.com/UB-Mannheim/tesseract/wiki
   - 安装时勾选「Chinese (Simplified)」语言包（chi_sim），否则无法识别中文截图
   - 记下安装路径下的 `tesseract.exe`（通常在 `C:\\Program Files\\Tesseract-OCR\\tesseract.exe`）

3. 如果 `tesseract.exe` 不在系统 PATH 中，在 `config/wechat_groups.json` 的
   `ocr.tesseract_cmd` 填入完整路径，例如：
   ```json
   "ocr": {{
     "tesseract_cmd": "C:\\\\Program Files\\\\Tesseract-OCR\\\\tesseract.exe",
     "lang": "chi_sim+eng"
   }}
   ```

4. 重新运行：
   ```
   python src/ocr_extract.py --week {week}
   ```

## 截图清单（待识别，共 {screenshot_count} 张）

{screenshot_list}
"""


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="本地 OCR 提取（读取截图 manifest，输出 ocr_text.md）")
    parser.add_argument("--week", required=True, help="周数，如 2026-W24")
    parser.add_argument("--force", action="store_true", help="忽略 ocr_cache.json，全部重新识别")
    parser.add_argument("--config", default=str(common.DEFAULT_CONFIG_PATH), help="配置文件路径")
    return parser.parse_args(argv)


def iter_screenshots(manifest: dict):
    """遍历 manifest 里所有截图，按 (group_id, label, entry) 产出，保持采集顺序。"""
    for group_id, group_state in manifest.get("groups", {}).items():
        name = group_state.get("name", group_id)
        role = group_state.get("role", "")
        for entry in group_state.get("screens", []):
            yield group_id, f"{name}（{role}）", "main", entry
        for date, backfill_state in group_state.get("backfills", {}).items():
            for entry in backfill_state.get("screens", []):
                yield group_id, f"{name}（{role}）· 补采 {date}", f"backfill_{date}", entry


def write_placeholder(week: str, reason: str, manifest: dict) -> None:
    screenshots = list(iter_screenshots(manifest))
    lines = [f"- {entry['file']}" for _, _, _, entry in screenshots]
    content = PLACEHOLDER_TEMPLATE.format(
        week=week,
        reason=reason,
        screenshot_count=len(screenshots),
        screenshot_list="\n".join(lines) if lines else "（暂无，先运行 wechat_capture_bot.py 采集截图）",
    )
    common.ocr_text_path(week).write_text(content, encoding="utf-8")


def get_ocr_engine(config: dict):
    """返回 (image_to_string 函数, lang, 引擎描述) 或抛出 RuntimeError 说明原因。"""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:
        raise RuntimeError(
            f"Python 依赖未安装（{e}）。请先运行 `pip install -r requirements.txt`。"
        )

    ocr_cfg = config.get("ocr", {}) or {}
    tesseract_cmd = ocr_cfg.get("tesseract_cmd")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    try:
        version = pytesseract.get_tesseract_version()
    except Exception as e:
        raise RuntimeError(
            f"找不到 Tesseract-OCR 本体（{e}）。pytesseract 已安装，但调用不到 tesseract.exe，"
            f"请安装 Tesseract-OCR 并在 config/wechat_groups.json 的 ocr.tesseract_cmd 中指定路径。"
        )

    lang = ocr_cfg.get("lang", "chi_sim+eng")

    def _image_to_string(path: Path) -> str:
        with Image.open(path) as img:
            return pytesseract.image_to_string(img, lang=lang)

    return _image_to_string, lang, f"tesseract {version}"


def main(argv=None) -> int:
    args = parse_args(argv)
    config = common.load_config(Path(args.config))
    week = args.week

    manifest = common.load_manifest(week)
    if not manifest.get("groups"):
        print(f"[错误] {common.manifest_path(week)} 里没有任何分组/截图记录，请先运行 wechat_capture_bot.py。", file=sys.stderr)
        return 1

    try:
        image_to_string, lang, engine_desc = get_ocr_engine(config)
    except RuntimeError as e:
        write_placeholder(week, str(e), manifest)
        print(f"[错误] {e}", file=sys.stderr)
        print(f"已写入占位说明：{common.ocr_text_path(week)}", file=sys.stderr)
        return 1

    cache: dict = common.load_json(common.ocr_cache_path(week), default={})
    if args.force:
        cache = {}

    screenshots = list(iter_screenshots(manifest))
    new_count = 0
    for _, _, _, entry in screenshots:
        sha = entry["sha256"]
        if sha in cache:
            continue
        img_path = common.PROJECT_ROOT / entry["file"]
        if not img_path.exists():
            cache[sha] = f"[警告：截图文件不存在 {entry['file']}]"
            continue
        text = image_to_string(img_path)
        cache[sha] = text
        new_count += 1
        if new_count % 5 == 0:
            common.write_json(common.ocr_cache_path(week), cache)
            print(f"  ... 已识别 {new_count} 张新截图")

    common.write_json(common.ocr_cache_path(week), cache)

    # 生成 ocr_text.md
    lines = [f"# OCR 文本提取 · {week}", "", f"> 引擎：{engine_desc} ｜ lang: {lang}", ""]
    current_section = None
    for group_id, label, scope, entry in screenshots:
        section_key = (group_id, scope)
        if section_key != current_section:
            lines.append(f"## {label}")
            lines.append("")
            current_section = section_key
        text = cache.get(entry["sha256"], "").strip()
        rel = entry["file"]
        lines.append(f"### {rel}")
        lines.append("```")
        lines.append(text if text else "(空)")
        lines.append("```")
        lines.append("")

    common.ocr_text_path(week).write_text("\n".join(lines), encoding="utf-8")

    print(f"完成：共 {len(screenshots)} 张截图，本次新识别 {new_count} 张（其余命中缓存）。")
    print(f"输出：{common.ocr_text_path(week)}")
    print("下一步：运行 src/event_detector.py 做规则筛选。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
