#!/usr/bin/env python3
"""批量转写 B 站合集：逐集下载音频 → whisper 转写 → 删除音频 → 产出 transcript.md。

用法：
  python batch_transcribe.py <BV号> --from 1 --to 88 --outdir <合集目录>
已存在 transcript.md 的分 P 会自动跳过（断点续跑）。失败的集会记录下来，最后统一报告。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

from _paths import CACHE_DIR, VENV_PY

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def get_pages(bvid):
    req = urllib.request.Request(
        f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
        headers={"User-Agent": UA, "Referer": "https://www.bilibili.com"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    if data.get("code") != 0:
        sys.exit(f"错误：view API 返回 {data.get('code')} {data.get('message')}")
    return data["data"]["title"], data["data"]["pages"]


def sanitize(name):
    return re.sub(r'[\\/:*?"<>|\r\n]+', "_", name).strip() or "untitled"


def main():
    ap = argparse.ArgumentParser(description="批量转写 B 站合集")
    ap.add_argument("video", help="BV 号或链接")
    ap.add_argument("--from", dest="start", type=int, default=1)
    ap.add_argument("--to", dest="end", type=int, default=10**9)
    ap.add_argument("--outdir", required=True, help="合集输出目录")
    ap.add_argument("--model", default="small")
    args = ap.parse_args()

    m = re.search(r"(BV[0-9A-Za-z]{10})", args.video)
    if not m:
        sys.exit("错误：无法解析 BV 号")
    bvid = m.group(1)

    series_title, pages = get_pages(bvid)
    total = len(pages)
    print(f"合集《{series_title}》共 {total} P，本次处理 P{args.start}~P{min(args.end, total)}",
          flush=True)

    failed = []
    done = skipped = 0
    for p in pages:
        n = p["page"]
        if n < args.start or n > args.end:
            continue
        folder = os.path.join(args.outdir, f"P{n}-{sanitize(p['part'])}")
        transcript = os.path.join(folder, "transcript.md")
        if os.path.exists(transcript):
            print(f"[P{n}] 已存在，跳过", flush=True)
            skipped += 1
            continue
        os.makedirs(folder, exist_ok=True)
        t0 = time.time()
        print(f"[P{n}] {p['part']}（{p['duration'] // 60}分{p['duration'] % 60}秒）开始……",
              flush=True)
        try:
            r = subprocess.run(
                [sys.executable, os.path.join(SCRIPTS, "download_audio.py"), bvid,
                 "--page", str(n)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=900)
            if r.returncode != 0:
                raise RuntimeError(f"下载失败：{r.stderr.strip()[:200]}")

            r = subprocess.run(
                [VENV_PY, os.path.join(SCRIPTS, "transcribe.py"),
                 os.path.join(CACHE_DIR, "audio.m4a"),
                 "-o", transcript, "--model", args.model,
                 "--title", f"{p['part']}（{series_title} P{n}）"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=3600)
            if r.returncode != 0:
                raise RuntimeError(f"转写失败：{r.stderr.strip()[:200]}")
            done += 1
            print(f"[P{n}] 完成，耗时 {time.time() - t0:.0f}s", flush=True)
        except Exception as e:
            failed.append((n, str(e)))
            print(f"[P{n}] 失败：{e}", flush=True)
        finally:
            cache_audio = os.path.join(CACHE_DIR, "audio.m4a")
            if os.path.exists(cache_audio):
                os.remove(cache_audio)
        time.sleep(2)  # 轻微限速，防止触发 B 站风控

    print(f"\n=== 汇总：成功 {done}，跳过 {skipped}，失败 {len(failed)} ===", flush=True)
    for n, err in failed:
        print(f"  P{n}: {err}", flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
