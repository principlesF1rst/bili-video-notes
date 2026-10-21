#!/usr/bin/env python3
"""校验 notes.md 对 transcript.md 的覆盖度，防止结构化时丢内容。

检查项：
1. 时间覆盖：notes.md 中每个章节必须有 `> ⏱ 开始-结束` 锚点（多 P 视频写作 `> ⏱ P2 03:00-09:10`），
   合并后对比每个分 P 的实际时长，空洞超过阈值即报错。
2. 术语覆盖：从转录中提取《》引用词和英文/数字术语，检查是否出现在 notes.md 中（仅警告）。

退出码：0 = 通过；1 = 存在时间空洞。
"""
import argparse
import re
import sys


def parse_ts(s):
    parts = [int(x) for x in s.split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def fmt(t):
    t = int(t)
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def main():
    ap = argparse.ArgumentParser(description="检查笔记对转录的时间/术语覆盖度")
    ap.add_argument("transcript", help="transcript.md 路径")
    ap.add_argument("notes", help="notes.md 路径")
    ap.add_argument("--gap", type=int, default=60, help="允许的最大空洞秒数（默认 60）")
    args = ap.parse_args()

    with open(args.transcript, encoding="utf-8") as f:
        transcript = f.read()
    with open(args.notes, encoding="utf-8") as f:
        notes = f.read()

    # 每个分 P 的最后一条时间戳 = 该 P 实际内容长度
    sections = re.split(r"^## P(\d+) ", transcript, flags=re.M)
    durations = {}
    it = iter(sections[1:])
    for pnum, body in zip(it, it):
        ts = re.findall(r"^\[(\d{2}:\d{2}:\d{2})\]", body, flags=re.M)
        if ts:
            durations[int(pnum)] = parse_ts(ts[-1])
    if not durations:  # 单段转写（whisper 产物没有 ## P 分节）
        ts = re.findall(r"^\[(\d{2}:\d{2}:\d{2})\]", transcript, flags=re.M)
        if ts:
            durations[1] = parse_ts(ts[-1])
    if not durations:
        sys.exit("错误：transcript 中没有找到任何时间戳")

    anchors = re.findall(
        r"⏱\s*(?:P(\d+)\s*)?(\d{1,2}:\d{2}(?::\d{2})?)-(\d{1,2}:\d{2}(?::\d{2})?)", notes)
    if not anchors:
        sys.exit("错误：notes.md 中没有任何 `> ⏱ 开始-结束` 时间锚点，无法校验覆盖度")

    ranges = {}
    for p, a, b in anchors:
        ranges.setdefault(int(p) if p else 1, []).append((parse_ts(a), parse_ts(b)))

    ok = True
    for p in sorted(durations):
        end = durations[p]
        covered = sorted(ranges.get(p, []))
        merged = []
        for a, b in covered:
            if merged and a <= merged[-1][1] + 5:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        gaps = []
        cursor = 0
        for a, b in merged:
            if a - cursor > args.gap:
                gaps.append((cursor, a))
            cursor = max(cursor, b)
        if end - cursor > args.gap:
            gaps.append((cursor, end))
        if gaps:
            ok = False
            print(f"P{p} 存在未覆盖时间段：")
            for a, b in gaps:
                print(f"  - {fmt(a)} ~ {fmt(b)}")
    if ok:
        print("时间覆盖：通过（所有分 P 均被笔记覆盖）")

    quoted = set(re.findall(r"《([^》\n]{2,20})》", transcript))
    latin = set(w for w in re.findall(r"[A-Za-z][A-Za-z0-9+.#-]{2,}", transcript)
                if not w.lower().startswith(("http", "www")))
    missing = sorted(t for t in quoted | latin if t not in notes)
    if missing:
        print(f"术语提醒：以下 {len(missing)} 个转录中的术语未出现在笔记里（请确认是否应补充）：")
        for t in missing[:30]:
            print(f"  - {t}")
    else:
        print("术语覆盖：通过")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
