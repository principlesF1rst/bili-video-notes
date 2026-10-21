#!/usr/bin/env python3
"""用 yt-dlp 下载视频音频，供 whisper 降级转写使用。最后一行输出 AUDIO=<路径>。"""
import argparse
import glob
import os
import subprocess
import sys

from _paths import CACHE_DIR, COOKIE_FILE, YT_DLP


def resolve_cookie(arg_cookie):
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


def main():
    ap = argparse.ArgumentParser(description="下载 B 站视频音频（m4a）")
    ap.add_argument("video", help="BV 号或视频链接")
    ap.add_argument("-o", "--outdir", default=CACHE_DIR,
                    help=f"输出目录（默认缓存目录 {CACHE_DIR}）")
    ap.add_argument("--page", type=int, default=0, help="第 N 个分 P（默认 0 = 按链接原样）")
    ap.add_argument("--cookie", default=None,
                    help=f"登录 cookie（会员/登录可见视频需要）；也可用环境变量或 {COOKIE_FILE}")
    args = ap.parse_args()

    if not os.path.exists(YT_DLP):
        sys.exit(f"错误：找不到 yt-dlp：{YT_DLP}")
    os.makedirs(args.outdir, exist_ok=True)
    cookie = resolve_cookie(args.cookie)

    url = args.video
    if url.startswith("BV"):
        url = f"https://www.bilibili.com/video/{url}"
    if args.page:
        url += f"?p={args.page}"

    for old in glob.glob(os.path.join(args.outdir, "audio.*")):
        os.remove(old)

    cmd = [YT_DLP, "-f", "ba/b", "-x", "--audio-format", "m4a", "--no-playlist",
           "--ffmpeg-location", os.path.join(os.path.dirname(YT_DLP), "ffmpeg", "bin"),
           "-o", os.path.join(args.outdir, "audio.%(ext)s"), url]
    if cookie:
        cmd += ["--add-header", f"Cookie:{cookie}"]
    print("执行:", " ".join(cmd), file=sys.stderr)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        sys.exit(f"错误：yt-dlp 下载失败（退出码 {r.returncode}）")

    hits = glob.glob(os.path.join(args.outdir, "audio.*"))
    if not hits:
        sys.exit("错误：未找到下载产物")
    print(f"AUDIO={hits[0]}")


if __name__ == "__main__":
    main()
