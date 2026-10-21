#!/usr/bin/env python3
"""通用章节合并：把课程目录下「中间产物」里的分集笔记，按 chapters.json 合并到「笔记」。

标准课程目录：
  <课程目录>/
  ├── 中间产物/          # P{n}-标题/transcript.md + notes.md
  ├── 笔记/              # 输出：章节合并 md（用户看的最终版）
  └── chapters.json      # 章节划分配置

chapters.json 格式：
{
  "series": "课程名（可省略）",
  "chapters": [
    {"name": "09-索引", "from": 66, "to": 88},
    {"name": "06-总结", "episodes": [57, 58]}
  ]
}

用法：
  python merge_chapters.py <课程目录> [--config <chapters.json路径>]

特性：纯组装不改写分集内容；每次全量重新生成，幂等；写完后校验所有分集跳转链接，失效则退出码 1。
"""
import argparse
import glob
import json
import os
import re
import sys


def sanitize(name):
    return re.sub(r'[\\/:*?"<>|\r\n]+', "_", name).strip() or "untitled"


def shift_headings(md):
    """去掉首个 H1，其余 markdown 标题降一级；代码围栏内的内容不动。"""
    lines = md.split("\n")
    out = []
    in_fence = False
    h1_removed = False
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if not in_fence:
            if not h1_removed and line.startswith("# "):
                h1_removed = True
                continue
            if re.match(r"^#{2,6}\s", line):
                line = "#" + line
        out.append(line)
    return "\n".join(out).strip("\n")


def chapter_episodes(ch):
    if "episodes" in ch:
        return list(ch["episodes"])
    return list(range(int(ch["from"]), int(ch["to"]) + 1))


def main():
    ap = argparse.ArgumentParser(description="按 chapters.json 合并课程章节笔记")
    ap.add_argument("course_dir", help="课程目录")
    ap.add_argument("--config", default=None, help="chapters.json 路径（默认课程目录下）")
    args = ap.parse_args()

    course_dir = os.path.abspath(args.course_dir)
    config_path = args.config or os.path.join(course_dir, "chapters.json")
    if not os.path.exists(config_path):
        sys.exit(f"错误：找不到章节配置 {config_path}")
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)
    chapters = config.get("chapters")
    if not chapters:
        sys.exit("错误：chapters.json 里没有 chapters 列表")
    series = config.get("series") or "视频合集"

    episode_root = os.path.join(course_dir, "中间产物")
    if not os.path.isdir(episode_root):
        if glob.glob(os.path.join(course_dir, "P*")):
            print("警告：未找到「中间产物」，回退到课程目录根下查找 P* 分集", file=sys.stderr)
            episode_root = course_dir
        else:
            sys.exit(f"错误：找不到分集目录 {episode_root}")
    out_dir = os.path.join(course_dir, "笔记")
    os.makedirs(out_dir, exist_ok=True)

    def find_episode(n):
        hits = sorted(glob.glob(os.path.join(episode_root, f"P{n}-*")))
        for h in hits:
            if os.path.isdir(h):
                return h
        return None

    had_missing = False
    for ch in chapters:
        name = sanitize(ch["name"])
        pages = chapter_episodes(ch)
        toc, parts, missing = [], [], []
        for n in pages:
            folder = find_episode(n)
            notes_path = os.path.join(folder, "notes.md") if folder else None
            if not notes_path or not os.path.exists(notes_path):
                missing.append(n)
                continue
            title = os.path.basename(folder)[len(f"P{n}-"):].strip()
            display = re.sub(r"^\d+\.\s*", "", title)
            rel = os.path.relpath(folder, out_dir).replace(os.sep, "/")
            toc.append(f"- P{n} {display}（[分集笔记](<{rel}/notes.md>) · "
                       f"[完整转录](<{rel}/transcript.md>)）")
            with open(notes_path, encoding="utf-8") as f:
                body = shift_headings(f.read())
            parts.append(f"## P{n} {display}\n\n{body}")

        if missing:
            had_missing = True
            print(f"警告：{name} 缺少分集：{missing}", file=sys.stderr)
        if not parts:
            print(f"跳过：{name}（没有任何可用分集）", file=sys.stderr)
            continue

        first, last = pages[0], pages[-1]
        header = (f"# {name.split('-', 1)[1] if '-' in name else name}"
                  f"（{series} P{first}~P{last}）\n\n"
                  f"> 本文件由 {len(parts)} 集笔记合并而成，点击目录可跳转分集原始笔记与完整转录\n\n"
                  "## 本章节目录\n\n" + "\n".join(toc))
        content = header + "\n\n---\n\n" + "\n\n---\n\n".join(parts) + "\n"
        with open(os.path.join(out_dir, f"{name}.md"), "w", encoding="utf-8") as f:
            f.write(content)
        print(f"{name}.md  {len(parts)} 集  {len(content) // 1024}KB")

    broken = []
    link_count = 0
    for path in glob.glob(os.path.join(out_dir, "*.md")):
        text = open(path, encoding="utf-8").read()
        for target in re.findall(r"\]\(<([^>]+)>\)", text):
            link_count += 1
            if not os.path.exists(os.path.normpath(os.path.join(out_dir, target))):
                broken.append((os.path.basename(path), target))
    print(f"链接校验：{link_count} 条，失效 {len(broken)} 条")
    for src, target in broken[:20]:
        print(f"  失效：{src} -> {target}", file=sys.stderr)

    sys.exit(1 if (broken or had_missing) else 0)


if __name__ == "__main__":
    main()
