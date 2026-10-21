#!/usr/bin/env python3
"""共享路径约定：所有脚本统一从这里取工具目录。

解析优先级：
1. 环境变量 BILI_NOTE_TOOLS（指向任意工具目录）
2. 默认 <skill根目录>/tools（skill根目录 = scripts/ 的上一级）

工具目录内约定：
  yt-dlp(.exe) / ffmpeg/bin/ / whisper-venv/ / cache/ / bili_cookie.txt / .env_checked
"""
import os
import sys

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.environ.get("BILI_NOTE_TOOLS") or os.path.join(SKILL_ROOT, "tools")

_IS_WIN = sys.platform.startswith("win")

YT_DLP = os.path.join(TOOLS, "yt-dlp.exe" if _IS_WIN else "yt-dlp")
FFMPEG = os.path.join(TOOLS, "ffmpeg", "bin", "ffmpeg.exe" if _IS_WIN else "ffmpeg")
VENV_PY = os.path.join(
    TOOLS, "whisper-venv",
    "Scripts" if _IS_WIN else "bin",
    "python.exe" if _IS_WIN else "python")
COOKIE_FILE = os.path.join(TOOLS, "bili_cookie.txt")
CACHE_DIR = os.path.join(TOOLS, "cache")
ENV_MARKER = os.path.join(TOOLS, ".env_checked")
