#!/usr/bin/env python3
"""环境自检：检查 bili-video-notes 依赖是否齐全。退出码 0 = 可用，1 = 有缺失。

只检查不安装。缺失项的安装引导和体积说明见 SKILL.md 第 0 步。
"""
import os
import subprocess
import sys

from _paths import COOKIE_FILE as COOKIE
from _paths import ENV_MARKER as MARKER
from _paths import FFMPEG, TOOLS, VENV_PY, YT_DLP

# 已通过完整检查则走快速路径：不必每条链接都重检。--force 强制重新完整检查。
if "--force" not in sys.argv and os.path.exists(MARKER) \
        and os.path.exists(YT_DLP) and os.path.exists(FFMPEG):
    print("✅ 环境已在此前验证通过，跳过详细检查（--force 可强制重检）")
    sys.exit(0)

ok = True


def run(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return (r.stdout or r.stderr or "").strip().split("\n")[0][:80]
    except Exception as e:
        return f"运行失败：{e}"


def check(name, path, version_cmd=None, required=True):
    global ok
    if not os.path.exists(path):
        print(f"❌ {name}：缺失（{path}）")
        if required:
            ok = False
        return
    info = f"：{run(version_cmd)}" if version_cmd else ""
    print(f"✅ {name}{info}")


check("yt-dlp", YT_DLP, [YT_DLP, "--version"])
check("ffmpeg", FFMPEG, [FFMPEG, "-version"])

if not os.path.exists(VENV_PY):
    print(f"ℹ️  whisper-venv：未安装（{VENV_PY}）")
    print("    faster-whisper 为可选组件：仅当需要处理无官方字幕的视频时才安装；"
          "不装则无法处理无字幕视频")
else:
    r = subprocess.run(
        [VENV_PY, "-c",
         "import faster_whisper, av, ctranslate2; "
         "print(f'faster-whisper {faster_whisper.__version__} / av {av.__version__} / "
         "CUDA设备数 {ctranslate2.get_cuda_device_count()}')"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if r.returncode != 0:
        print(f"❌ faster-whisper 环境异常：{(r.stderr or '').strip()[:120]}")
        ok = False
    else:
        line = r.stdout.strip()
        print(f"✅ whisper 环境：{line}")
        if "CUDA设备数 0" in line:
            print("ℹ️  未检测到可用 CUDA（将走 CPU/int8）；如有 N 卡想启用，"
                  "需装 nvidia-cublas-cu12 和 nvidia-cudnn-cu12 到 whisper-venv")

if os.path.exists(COOKIE):
    print("✅ B站 cookie 已配置（可抓官方字幕）")
else:
    print(f"ℹ️  未配置 B站 cookie（{COOKIE}），无字幕视频将走 whisper 转写")

print()
if ok:
    import datetime
    with open(MARKER, "w", encoding="utf-8") as f:
        f.write(f"env checked ok at {datetime.datetime.now().isoformat(timespec='seconds')}\n")
    print("环境就绪，可以开始处理视频。（已写入通过标记，后续无需重复检查）")
else:
    print("环境有缺失，请先按 SKILL.md 第 0 步完成安装（下载前需征得用户同意）。")
sys.exit(0 if ok else 1)
