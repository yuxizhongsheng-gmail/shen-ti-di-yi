#!/usr/bin/env python3
"""IP 群高光 · 截图目录扫描 -> capture_manifest.json

扫描 inbox/adb_captures/<week>/<group_id>/ 下的图片，
建立 runs/<week>/capture_manifest.json 供后续 OCR 和事件检测使用。

截图放置规则：
  inbox/adb_captures/2026-W24/main/     ← 🌲25IP训练营交流群截图（按时间顺序命名）
  inbox/adb_captures/2026-W24/trigger/  ← 【禁言ing】IP大大大群（可选）

图片文件名任意，按文件名自然排序（推荐 0001.png 命名）。

用法：
    python src/build_manifest.py --week 2026-W24
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import common

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="扫描截图目录，建立 capture_manifest.json")
    p.add_argument("--week", required=True, help="周数，如 2026-W24")
    p.add_argument("--config", default=str(common.DEFAULT_CONFIG_PATH))
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    config = common.load_config(Path(args.config))
    week = args.week

    captures_root = common.PROJECT_ROOT / "inbox" / "adb_captures" / week

    manifest = {
        "week": week,
        "scanned_at": common.now_iso(),
        "source_dir": str(captures_root.relative_to(common.PROJECT_ROOT)),
        "groups": {},
    }

    total = 0
    for group_cfg in config.get("groups", []):
        gid = group_cfg["id"]
        gname = group_cfg["name"]
        grole = group_cfg.get("role", "")

        group_dir = captures_root / gid
        group_dir.mkdir(parents=True, exist_ok=True)

        images = sorted(
            p for p in group_dir.iterdir()
            if p.suffix.lower() in IMAGE_SUFFIXES and not p.name.startswith(".")
        )

        screens = []
        for i, img_path in enumerate(images, start=1):
            try:
                data = img_path.read_bytes()
                sha = hashlib.sha256(data).hexdigest()
            except OSError as e:
                print(f"  ⚠️  读取失败，跳过 {img_path.name}: {e}", file=sys.stderr)
                continue
            screens.append({
                "index": i,
                "file": str(img_path.relative_to(common.PROJECT_ROOT)),
                "sha256": sha,
                "captured_at": common.now_iso(),
            })

        manifest["groups"][gid] = {
            "name": gname,
            "role": grole,
            "muted": group_cfg.get("muted", False),
            "status": "ready" if screens else "empty",
            "screens": screens,
            "backfills": {},
        }

        n = len(screens)
        status = f"{n} 张截图" if n else "（空，跳过）"
        print(f"  [{gid}] {gname}: {status}")
        total += n

    common.save_manifest(week, manifest)
    print(f"\n✅ capture_manifest.json -> {common.manifest_path(week)}")

    if total == 0:
        print(f"\n⚠️  还没有截图。请把截图放进：")
        print(f"   inbox/adb_captures/{week}/main/     （主群截图，按时间顺序）")
        print(f"   inbox/adb_captures/{week}/trigger/  （触发源群截图，可选）")
        print(f"   然后重新运行：python src/build_manifest.py --week {week}")
    else:
        print(f"   共 {total} 张。下一步：python src/ocr_extract.py --week {week}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
