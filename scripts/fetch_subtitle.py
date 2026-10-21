#!/usr/bin/env python3
"""抓取 B 站视频信息与官方 CC/AI 字幕，输出带时间戳的 transcript.md。

退出码：0 = 成功；2 = 所有分 P 均无官方字幕（调用方应走 whisper 转写）；1 = 其他错误。
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

from _paths import COOKIE_FILE


def resolve_cookie(arg_cookie):
    """优先级：--cookie 参数 > BILI_COOKIE/SESSDATA 环境变量 > cookie 文件。"""
    if arg_cookie:
        return arg_cookie
    env = os.environ.get("BILI_COOKIE")
    if env:
        return env
    if os.environ.get("SESSDATA"):
        return f"SESSDATA={os.environ['SESSDATA']}"
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE, encoding="utf-8") as f:
            content = f.read().strip()
        if content and "SESSDATA" not in content and "=" not in content:
            content = f"SESSDATA={content}"
        return content or None
    return None


def http_get_json(url, cookie=None):
    headers = {"User-Agent": UA, "Referer": "https://www.bilibili.com"}
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def parse_bvid(text):
    m = re.search(r"(BV[0-9A-Za-z]{10})", text)
    if not m:
        sys.exit("错误：无法从输入中解析 BV 号")
    return m.group(1)


def fmt(t):
    t = int(float(t))
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def sanitize(name):
    return re.sub(r'[\\/:*?"<>|\r\n]+', "_", name).strip() or "untitled"


def pick_subtitle(subs):
    if not subs:
        return None
    zh = [s for s in subs if "zh" in s.get("lan", "")]
    pool = zh or subs
    human = [s for s in pool if "ai_subtitle" not in s.get("subtitle_url", "")]
    return (human or pool)[0]


def main():
    ap = argparse.ArgumentParser(description="抓取 B 站官方字幕生成 transcript.md")
    ap.add_argument("video", help="BV 号或视频链接")
    ap.add_argument("-o", "--outdir", default=".", help="输出目录（默认当前目录）")
    ap.add_argument("--cookie", default=None,
                    help=f"登录 cookie（AI 字幕常需登录）；也可用环境变量 BILI_COOKIE/SESSDATA，"
                         f"或把 SESSDATA 写入 {COOKIE_FILE}")
    ap.add_argument("--page", type=int, default=0, help="只抓第 N 个分 P（默认 0 = 全部）")
    args = ap.parse_args()

    bvid = parse_bvid(args.video)
    cookie = resolve_cookie(args.cookie)

    try:
        view = http_get_json(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
                             cookie)
    except urllib.error.URLError as e:
        sys.exit(f"错误：无法访问 B 站 API：{e}")
    if view.get("code") != 0:
        sys.exit(f"错误：view API 返回 code={view.get('code')} {view.get('message')}")

    data = view["data"]
    title = data["title"]
    pages = data["pages"]
    if args.page:
        pages = [p for p in pages if p["page"] == args.page]
        if not pages:
            sys.exit(f"错误：不存在第 {args.page} 个分 P")

    out_lines = [
        f"# {title}",
        "",
        f"- BV: {bvid}",
        f"- UP主: {data.get('owner', {}).get('name', '')}",
        f"- 链接: https://www.bilibili.com/video/{bvid}",
        f"- 总时长: {fmt(data.get('duration', 0))}",
        f"- 分P数: {len(data['pages'])}",
        "",
    ]
    got_any = False
    for p in pages:
        out_lines.append(f"## P{p['page']} {p['part']}")
        out_lines.append("")
        try:
            player = http_get_json(
                f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={p['cid']}",
                cookie)
        except urllib.error.URLError as e:
            print(f"警告：P{p['page']} player API 失败：{e}", file=sys.stderr)
            continue
        subs = (player.get("data") or {}).get("subtitle", {}).get("subtitles") or []
        sub = pick_subtitle(subs)
        if not sub:
            print(f"提示：P{p['page']} 无官方字幕", file=sys.stderr)
            continue
        url = sub["subtitle_url"]
        if url.startswith("//"):
            url = "https:" + url
        try:
            sub_json = http_get_json(url, cookie)
        except urllib.error.URLError as e:
            print(f"警告：P{p['page']} 字幕下载失败：{e}", file=sys.stderr)
            continue
        body = sub_json.get("body") or []
        print(f"P{p['page']} 使用字幕：{sub.get('lan_doc', sub.get('lan'))}，共 {len(body)} 条",
              file=sys.stderr)
        for item in body:
            content = str(item.get("content", "")).replace("\n", " ").strip()
            if content:
                out_lines.append(f"[{fmt(item.get('from', 0))}] {content}")
        out_lines.append("")
        got_any = True

    if not got_any:
        print("无官方字幕", file=sys.stderr)
        sys.exit(2)

    outdir = os.path.join(args.outdir, sanitize(title))
    os.makedirs(outdir, exist_ok=True)
    out_path = os.path.join(outdir, "transcript.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))
    print(f"TRANSCRIPT={out_path}")
    print(f"TITLE={title}")


if __name__ == "__main__":
    main()
