#!/usr/bin/env python3
"""IP 群高光 · Day 1 截图采集模块

ADB 控制手机连续截图 + 滚动，保存到 runs/{week}/screenshots/。
不调用任何 LLM API。

用法：
    python src/phone_capture.py --week 2026-W24
    python src/phone_capture.py --week 2026-W24 --count 40 --delay 1.0
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

import common

DEFAULT_COUNT = 80
DEFAULT_DELAY = 0.8
DEFAULT_SWIPE = {
    "from_x": 0.5, "from_y": 0.75,
    "to_x": 0.5, "to_y": 0.25,
    "duration_ms": 300,
}


def screenshots_dir(week: str) -> Path:
    d = common.week_dir(week) / "screenshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_yaml_config() -> dict:
    yaml_path = common.CONFIG_DIR / "ip_highlight.yaml"
    if not yaml_path.exists():
        return {}
    try:
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        return _parse_yaml_fallback(yaml_path)


def _parse_yaml_fallback(path: Path) -> dict:
    """Minimal YAML-like parser for flat/simple configs when PyYAML unavailable."""
    result: dict = {}
    try:
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.split("#")[0].strip()
            if not line or ":" not in line:
                continue
            key, _, val = line.partition(":")
            val = val.strip().strip('"').strip("'")
            if val.lower() == "null":
                val = None
            elif val.isdigit():
                val = int(val)
            else:
                try:
                    val = float(val)
                except ValueError:
                    pass
            result[key.strip()] = val
    except Exception:
        pass
    return result


def doctor(config: dict) -> tuple[str, str, tuple[int, int]]:
    """Check ADB connection. Returns (adb_path, serial, screen_size)."""
    device_cfg = config.get("device") or {}
    wechat_cfg = common.load_config()

    adb_path = common.resolve_adb_path(wechat_cfg)
    serial_hint = device_cfg.get("serial") or (wechat_cfg.get("device") or {}).get("serial")

    print("🔍 检查 ADB ...")
    serial = common.check_device(adb_path, serial_hint)
    print(f"  ✅ 设备已连接: {serial}")

    screen_size = common.get_screen_size(adb_path, serial)
    print(f"  ✅ 屏幕分辨率: {screen_size[0]}x{screen_size[1]}")

    return adb_path, serial, screen_size


def capture(week: str, config: dict, count: int | None = None,
            delay: float | None = None) -> dict:
    """Run ADB capture loop. Returns manifest dict."""
    adb_path, serial, screen_size = doctor(config)
    w, h = screen_size

    cap_cfg = config.get("capture") or {}
    swipe_cfg = cap_cfg.get("swipe") or DEFAULT_SWIPE
    n = count or cap_cfg.get("screenshot_count") or DEFAULT_COUNT
    d = delay or cap_cfg.get("delay_seconds") or DEFAULT_DELAY

    sx1 = int(swipe_cfg.get("from_x", 0.5) * w)
    sy1 = int(swipe_cfg.get("from_y", 0.75) * h)
    sx2 = int(swipe_cfg.get("to_x", 0.5) * w)
    sy2 = int(swipe_cfg.get("to_y", 0.25) * h)
    dur = swipe_cfg.get("duration_ms", 300)

    out_dir = screenshots_dir(week)

    print(f"\n📸 开始截图采集: {n} 张, 间隔 {d}s")
    print(f"   输出目录: {out_dir}")
    print(f"   滑动: ({sx1},{sy1}) → ({sx2},{sy2}), {dur}ms")
    print()
    print("⚠️  请确保手机微信已打开到目标群的本周聊天位置。")
    print("   准备好后按 Enter 开始 ...")

    try:
        input()
    except EOFError:
        pass

    manifest = {
        "week": week,
        "started_at": common.now_iso(),
        "finished_at": None,
        "screenshot_count": 0,
        "screenshot_paths": [],
        "adb_device": serial,
        "swipe_config": {
            "from": [sx1, sy1], "to": [sx2, sy2], "duration_ms": dur,
        },
        "screen_size": list(screen_size),
        "status": "capturing",
    }

    prev_hash = None
    dup_count = 0

    for i in range(1, n + 1):
        fname = f"{i:03d}.png"
        fpath = out_dir / fname

        try:
            sha = common.screenshot(adb_path, serial, fpath)
        except common.AdbError as e:
            print(f"  ❌ 截图 {fname} 失败: {e}")
            break

        manifest["screenshot_paths"].append(str(fpath.relative_to(common.PROJECT_ROOT)))
        manifest["screenshot_count"] = i

        if sha == prev_hash:
            dup_count += 1
            if dup_count >= 3:
                print(f"  ⏹  连续 {dup_count} 张重复，已到底。停止截图。")
                break
        else:
            dup_count = 0
        prev_hash = sha

        print(f"  📷 {fname}  ({i}/{n})" + ("  ⚠️ 重复" if dup_count else ""))

        if i < n:
            common.swipe(adb_path, serial, sx1, sy1, sx2, sy2, dur)
            time.sleep(d)

    manifest["finished_at"] = common.now_iso()
    manifest["status"] = "completed"

    manifest_out = common.week_dir(week) / "capture_manifest.json"
    common.write_json(manifest_out, manifest)
    print(f"\n✅ 截图采集完成: {manifest['screenshot_count']} 张")
    print(f"   manifest: {manifest_out}")

    return manifest


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="IP 群高光 · 截图采集")
    p.add_argument("--week", required=True)
    p.add_argument("--count", type=int, default=None)
    p.add_argument("--delay", type=float, default=None)
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    config = load_yaml_config()
    try:
        capture(args.week, config, args.count, args.delay)
    except common.AdbError as e:
        print(f"\n❌ ADB 错误: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
