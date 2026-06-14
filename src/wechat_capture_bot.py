#!/usr/bin/env python3
"""IP 群高光 · 微信群截图采集 Bot

通过 ADB 控制手机当前可见界面：自动截图、自动滚动、保存到本地。
不调用任何大模型 API，不读取/破解微信数据库，只操作「手机屏幕上当前看得到的内容」。

人工配合的部分（无法自动化，也不应该自动化）：
- 在手机上打开微信，进入目标群聊
- 把聊天记录滚动到「本次采集窗口」最早的一条消息（即采集起点）
- 之后按 Enter，剩下的截图+滚动由 Bot 完成

用法：
    python src/wechat_capture_bot.py --week 2026-W24
    python src/wechat_capture_bot.py --week 2026-W24 --groups main
    python src/wechat_capture_bot.py --week 2026-W24 --backfill 2026-06-07 --groups trigger
    python src/wechat_capture_bot.py --week 2026-W24 --force
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import common


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="微信群截图采集 Bot（ADB 控制手机可见界面）")
    parser.add_argument("--week", required=True, help="周数，如 2026-W24")
    parser.add_argument("--groups", help="只采集指定的群 id，逗号分隔，如 main,trigger（默认采集配置中所有 enabled 的群）")
    parser.add_argument("--backfill", help="补采指定日期（YYYY-MM-DD），结果存入独立子目录，不影响本周主采集进度")
    parser.add_argument("--force", action="store_true", help="忽略已有的 completed 状态，重新采集（会清空该群已有截图记录）")
    parser.add_argument("--max-screens", type=int, help="覆盖配置中的 max_screens_per_group")
    parser.add_argument("--config", default=str(common.DEFAULT_CONFIG_PATH), help="配置文件路径")
    return parser.parse_args(argv)


def log_line(week: str, text: str) -> None:
    path = common.capture_log_path(week)
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    with open(path, "a", encoding="utf-8") as f:
        if is_new:
            f.write(f"# 采集日志 · {week}\n\n")
        f.write(text + "\n")
    print(text)


def capture_group(
    adb_path: str,
    serial: str,
    screen_size: tuple[int, int],
    group_cfg: dict,
    capture_cfg: dict,
    week: str,
    manifest: dict,
    force: bool,
    max_screens_override: int | None,
    backfill_date: str | None,
) -> None:
    group_id = group_cfg["id"]
    group_name = group_cfg["name"]
    role = group_cfg.get("role", "")

    groups_state = manifest.setdefault("groups", {})
    group_state = groups_state.setdefault(group_id, {
        "name": group_name,
        "role": role,
        "status": "not_started",
        "screens": [],
        "backfills": {},
    })
    group_state["name"] = group_name
    group_state["role"] = role

    if backfill_date:
        target_state = group_state["backfills"].setdefault(backfill_date, {
            "status": "not_started",
            "screens": [],
        })
        out_dir = common.captures_dir(week, group_id, backfill_date=backfill_date)
        label = f"{group_name}（{role}）· 补采 {backfill_date}"
    else:
        target_state = group_state
        out_dir = common.captures_dir(week, group_id)
        label = f"{group_name}（{role}）"

    if force:
        target_state["status"] = "not_started"
        target_state["screens"] = []

    if target_state.get("status") == "completed":
        log_line(week, f"\n## {label}\n- 已标记为 completed，跳过（如需重采，加 --force）")
        return

    existing_screens = target_state.get("screens", [])
    start_index = len(existing_screens) + 1

    log_line(week, f"\n## {label}")
    if start_index > 1:
        last_file = existing_screens[-1]["file"]
        log_line(
            week,
            f"- 检测到已采集 {len(existing_screens)} 张（断点续采）。"
            f"上次最后一张：{last_file}\n"
            f"- 请在手机上把该群滚动到与上次最后一张截图大致相同的位置（可以稍微往前一点，重复几张没关系），"
            f"然后按 Enter 继续。",
        )
    else:
        date_range = capture_cfg.get("date_range", {})
        if backfill_date:
            window_desc = f"补采日期 {backfill_date}"
        else:
            window_desc = f"{date_range.get('start', '?')} 至 {date_range.get('end', '?')}"
        log_line(
            week,
            f"- 请在手机上打开微信，进入「{group_name}」（{role}），"
            f"滚动到 {window_desc} 这段时间范围内【最早】的一条消息处。\n"
            f"- 准备好后按 Enter，Bot 将开始自动截图并向下滚动到最新消息。",
        )

    input(">>> 准备好后按 Enter 开始采集（Ctrl+C 可随时中断，进度会自动保存）... ")

    swipe_cfg = capture_cfg.get("swipe", {"from": [0.5, 0.8], "to": [0.5, 0.3], "duration_ms": 300})
    w, h = screen_size
    x1 = int(w * swipe_cfg["from"][0])
    y1 = int(h * swipe_cfg["from"][1])
    x2 = int(w * swipe_cfg["to"][0])
    y2 = int(h * swipe_cfg["to"][1])
    duration_ms = swipe_cfg.get("duration_ms", 300)

    max_screens = max_screens_override or capture_cfg.get("max_screens_per_group", 200)
    dup_threshold = capture_cfg.get("duplicate_stop_threshold", 3)
    scroll_delay = capture_cfg.get("scroll_delay_seconds", 1.0)

    recent_hashes: list[str] = [s["sha256"] for s in existing_screens[-dup_threshold:]]
    target_state["status"] = "in_progress"
    common.save_manifest(week, manifest)

    captured_this_run = 0
    try:
        for index in range(start_index, start_index + max_screens):
            out_path = out_dir / f"{index:04d}.png"
            sha = common.screenshot(adb_path, serial, out_path)
            entry = {
                "index": index,
                "file": str(out_path.relative_to(common.PROJECT_ROOT)),
                "sha256": sha,
                "captured_at": common.now_iso(),
            }
            target_state["screens"].append(entry)
            common.save_manifest(week, manifest)
            log_line(week, f"- 截图 {index:04d} 已保存 -> {entry['file']}")
            captured_this_run += 1

            recent_hashes.append(sha)
            if len(recent_hashes) > dup_threshold:
                recent_hashes.pop(0)
            if len(recent_hashes) == dup_threshold and len(set(recent_hashes)) == 1:
                log_line(
                    week,
                    f"- 连续 {dup_threshold} 张截图内容相同，判定已到达底部/无新内容，采集结束。",
                )
                target_state["status"] = "completed"
                common.save_manifest(week, manifest)
                break

            common.swipe(adb_path, serial, x1, y1, x2, y2, duration_ms)
            time.sleep(scroll_delay)
        else:
            log_line(week, f"- 已达到本群上限 {max_screens} 张，停止采集（未判定为 completed，可再次运行继续）。")
    except KeyboardInterrupt:
        target_state["status"] = "in_progress"
        common.save_manifest(week, manifest)
        log_line(week, f"- 用户中断，已保存 {captured_this_run} 张新截图，状态保留为 in_progress，可重新运行续采。")
        raise

    log_line(week, f"- 本次采集 {label} 共新增 {captured_this_run} 张，累计 {len(target_state['screens'])} 张。")


def main(argv=None) -> int:
    args = parse_args(argv)
    config = common.load_config(Path(args.config))
    capture_cfg = config.get("capture", {})

    adb_path = common.resolve_adb_path(config)
    serial = (config.get("device") or {}).get("serial")

    try:
        serial = common.check_device(adb_path, serial)
        screen_size = common.get_screen_size(adb_path, serial)
    except common.AdbError as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 1

    print(f"已连接设备：{serial}，屏幕尺寸：{screen_size[0]}x{screen_size[1]}")

    all_groups = [g for g in config.get("groups", []) if g.get("enabled", True)]
    if args.groups:
        wanted = set(args.groups.split(","))
        all_groups = [g for g in all_groups if g["id"] in wanted]
        if not all_groups:
            print(f"[错误] --groups 指定的群 id 在配置中找不到：{args.groups}", file=sys.stderr)
            return 1

    week = args.week
    manifest = common.load_manifest(week)
    manifest["week"] = week
    manifest.setdefault("date_range", capture_cfg.get("date_range"))
    manifest.setdefault("backfill_dates", capture_cfg.get("backfill_dates", []))
    manifest["updated_at"] = common.now_iso()

    for group_cfg in all_groups:
        capture_group(
            adb_path, serial, screen_size, group_cfg, capture_cfg, week, manifest,
            force=args.force,
            max_screens_override=args.max_screens,
            backfill_date=args.backfill,
        )

    common.save_manifest(week, manifest)
    print(f"\n完成。manifest: {common.manifest_path(week)}")
    print(f"日志: {common.capture_log_path(week)}")
    print("下一步：运行 src/ocr_extract.py 对截图做本地 OCR。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
