#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工序0·去噪压缩：把树林语料里的运营噪音剥掉，只留可能含思想的发言。
保守策略：宁可多留，不可错杀金句。短句只在"明显是闲聊/后勤"时才丢。
输出到 book/digest/_condensed/，供后续精读。"""
import re, sys, pathlib

SRC = pathlib.Path("corpus")
OUT = pathlib.Path("book/digest/_condensed")
OUT.mkdir(parents=True, exist_ok=True)

# 整条丢弃：后勤/运营/动员/媒体占位
LOGISTICS = re.compile(
    r"(直播|回放|几点|点半|视频号\]|小鹅通|课程安排|递延|更新|"
    r"名额|报名|订金|转账|收到|小助理|子渺|涛涛|晓昕|"
    r"踢掉?|红心|点赞|点起来|点喜欢|拍我|复制打开抖音|抖音|"
    r"\[图片\]|\[视频\]|\[文件\]|\[链接\]|\[语音\]|\.pdf|http|www\.|v\.douyin)"
)
# 纯闲聊：很短且没有实质中文（哈/数字/评分/单字/emoji/英文标点）
CHATTER = re.compile(r"^[\W\dA-Za-z哈呵嗯啊哦嘿嘻嗨嘤~、。，!！?？\shH]{0,11}$")

MSG = re.compile(r"^\*\*(\d{4}-\d{2}-\d{2})[^*]*\*\*\s*(.*)$")

def condense(path):
    kept, dropped = [], 0
    in_echo = False
    cur_date = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip("\n")
        # 丢弃转发回声块（--------- 包裹的「树林: ...」重复）
        if line.strip().startswith("---------------"):
            in_echo = not in_echo
            continue
        if in_echo or line.strip().startswith("「树林:"):
            continue
        m = MSG.match(line)
        if m:
            cur_date, content = m.group(1), m.group(2).strip()
            if not content:                      # 多行消息的起始空内容
                kept.append(("DATE", cur_date, ""))
                continue
            if LOGISTICS.search(content):
                dropped += 1; continue
            if CHATTER.match(content):
                dropped += 1; continue
            kept.append(("MSG", cur_date, content))
        else:
            # 多行消息的续行：跟随上一条是否保留
            if line.strip() == "" or line.startswith("#") or line.startswith(">"):
                continue
            if LOGISTICS.search(line) or CHATTER.match(line):
                continue
            kept.append(("CONT", cur_date, line.strip()))
    # 组装：按日期分组，续行并到上一条
    out_lines, last = [], None
    for kind, date, content in kept:
        if kind == "DATE":
            continue
        if kind == "MSG":
            out_lines.append(f"[{date}] {content}")
        else:
            if out_lines:
                out_lines[-1] += " / " + content
            else:
                out_lines.append(f"[{date}] {content}")
    return out_lines, dropped

total_in = total_out = 0
for path in sorted(SRC.glob("树林语料_*.md")):
    if "完整版" in path.name:
        continue
    lines, dropped = condense(path)
    text = "\n".join(lines)
    outp = OUT / path.name
    outp.write_text(text, encoding="utf-8")
    ci = len(path.read_text(encoding="utf-8")); co = len(text)
    total_in += ci; total_out += co
    print(f"{path.name:40s} {ci:8d} -> {co:8d}  ({co*100//ci:3d}%)  丢{dropped}条")
print(f"{'合计':40s} {total_in:8d} -> {total_out:8d}  ({total_out*100//total_in}%)")
