"""IP 群高光 · 采集/OCR/事件检测共用工具

提供：路径约定、配置加载、manifest 读写、adb 命令封装。
本模块不调用任何大模型 API。
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
RUNS_DIR = PROJECT_ROOT / "runs"

DEFAULT_CONFIG_PATH = CONFIG_DIR / "wechat_groups.json"
DEFAULT_RULES_PATH = CONFIG_DIR / "event_rules.json"


class AdbError(RuntimeError):
    """adb 命令执行失败"""


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# 配置 / JSON 读写
# ---------------------------------------------------------------------------

def load_json(path: Path, default=None):
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(f"找不到配置文件：{path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict:
    return load_json(path)


def load_rules(path: Path = DEFAULT_RULES_PATH) -> dict:
    return load_json(path)


# ---------------------------------------------------------------------------
# runs/<week> 目录约定
# ---------------------------------------------------------------------------

def week_dir(week: str) -> Path:
    d = RUNS_DIR / week
    d.mkdir(parents=True, exist_ok=True)
    return d


def captures_dir(week: str, group_id: str, backfill_date: str | None = None) -> Path:
    base = week_dir(week) / "captures" / group_id
    if backfill_date:
        base = base / f"backfill_{backfill_date}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def manifest_path(week: str) -> Path:
    return week_dir(week) / "capture_manifest.json"


def capture_log_path(week: str) -> Path:
    return week_dir(week) / "capture_log.md"


def ocr_text_path(week: str) -> Path:
    return week_dir(week) / "ocr_text.md"


def ocr_cache_path(week: str) -> Path:
    return week_dir(week) / "ocr_cache.json"


def candidate_events_path(week: str) -> Path:
    return week_dir(week) / "candidate_events.md"


def event_scores_path(week: str) -> Path:
    return week_dir(week) / "event_scores.json"


def load_manifest(week: str) -> dict:
    return load_json(manifest_path(week), default={"week": week, "groups": {}})


def save_manifest(week: str, manifest: dict) -> None:
    write_json(manifest_path(week), manifest)


# ---------------------------------------------------------------------------
# adb 封装
# ---------------------------------------------------------------------------

def resolve_adb_path(config: dict) -> str:
    """解析 adb 可执行文件路径。

    优先级：config.device.adb_path（项目内相对路径）
          -> tools/platform-tools/adb(.exe)
          -> 系统 PATH 中的 adb
    """
    configured = (config.get("device") or {}).get("adb_path")
    candidates = []
    if configured:
        candidates.append(PROJECT_ROOT / configured)
    candidates.append(PROJECT_ROOT / "tools" / "platform-tools" / "adb.exe")
    candidates.append(PROJECT_ROOT / "tools" / "platform-tools" / "adb")
    for c in candidates:
        if c.exists():
            return str(c)
    return "adb"


def adb_run(adb_path: str, serial: str | None, args: list[str], **kwargs):
    cmd = [adb_path]
    if serial:
        cmd += ["-s", serial]
    cmd += args
    kwargs.setdefault("capture_output", True)
    try:
        return subprocess.run(cmd, **kwargs)
    except FileNotFoundError:
        raise AdbError(
            f"找不到 adb 可执行文件（尝试的路径：{adb_path}）。\n"
            f"请下载 Android Platform Tools（见 tools/adb-setup.md），"
            f"把 adb.exe 放到 tools/platform-tools/ 下，或把 adb 加入系统 PATH。"
        )


def check_device(adb_path: str, serial: str | None) -> str:
    """确认有设备连接，返回设备序列号。"""
    result = adb_run(adb_path, None, ["devices"])
    if result.returncode != 0:
        stderr = (result.stderr or b"").decode("utf-8", "ignore")
        raise AdbError(
            f"无法运行 adb（路径：{adb_path}）。\n"
            f"请确认：1) adb.exe 已放在 tools/platform-tools/ 下，或在 PATH 中；"
            f"2) 手机已通过 USB 连接并开启「USB 调试」。\n"
            f"原始错误：{stderr}"
        )
    lines = [l.strip() for l in result.stdout.decode("utf-8", "ignore").splitlines()]
    devices = [l.split("\t")[0] for l in lines[1:] if l.strip().endswith("device")]
    if not devices:
        raise AdbError(
            "adb 已就绪，但没有检测到已连接的设备。\n"
            "请检查：手机是否用 USB 连接电脑、是否已开启「开发者选项 -> USB 调试」、"
            "并在手机上点击「允许此电脑调试」。\n"
            "运行 `adb devices` 应能看到设备序列号。"
        )
    if serial:
        if serial not in devices:
            raise AdbError(f"指定的设备 {serial} 未连接，当前连接的设备：{devices}")
        return serial
    if len(devices) > 1:
        raise AdbError(
            f"检测到多个设备：{devices}。请在 config/wechat_groups.json 的 "
            f"device.serial 中指定要使用的设备序列号。"
        )
    return devices[0]


def get_screen_size(adb_path: str, serial: str) -> tuple[int, int]:
    result = adb_run(adb_path, serial, ["shell", "wm", "size"])
    text = result.stdout.decode("utf-8", "ignore")
    match = re.search(r"(\d+)x(\d+)", text)
    if not match:
        raise AdbError(f"无法解析屏幕尺寸，adb shell wm size 输出：{text!r}")
    return int(match.group(1)), int(match.group(2))


def screenshot(adb_path: str, serial: str, out_path: Path) -> str:
    """截图并保存到 out_path，返回 PNG 字节的 sha256。"""
    import hashlib

    result = adb_run(adb_path, serial, ["exec-out", "screencap", "-p"])
    data = result.stdout
    if result.returncode != 0 or not data:
        stderr = (result.stderr or b"").decode("utf-8", "ignore")
        raise AdbError(f"截图失败：{stderr}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def swipe(adb_path: str, serial: str, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
    adb_run(
        adb_path, serial,
        ["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms)],
    )


def bring_wechat_foreground(adb_path: str, serial: str) -> None:
    """尝试把微信切到前台（不保证能定位到具体的群，需操作者手动进入目标群聊）。"""
    adb_run(
        adb_path, serial,
        ["shell", "monkey", "-p", "com.tencent.mm", "-c", "android.intent.category.LAUNCHER", "1"],
        check=False,
    )
