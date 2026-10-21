#!/usr/bin/env python3
"""用 faster-whisper 把音频转写成带时间戳的文本（格式与官方字幕 transcript 一致）。

必须用 whisper-venv 里的 python 运行：
  <TOOLS_DIR>/whisper-venv/Scripts/python.exe transcribe.py audio.m4a -o out.md
  （Windows 为 Scripts/python.exe，macOS/Linux 为 bin/python；TOOLS_DIR 见 _paths.py）
"""
import argparse
import os
import sys

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
# hf-mirror 是国内镜像，直连最快；走代理反而容易 SSL 断连
os.environ["NO_PROXY"] = (os.environ.get("NO_PROXY", "") + ",hf-mirror.com").strip(",")
# hf-mirror 不支持 xet 协议（会 401），强制走普通 HTTP 下载
os.environ["HF_HUB_DISABLE_XET"] = "1"


def register_cuda_dlls():
    """把 pip 安装的 nvidia-*-cu12 运行库目录加入 DLL 搜索路径（Windows 必需）。"""
    import site
    for sp in site.getsitepackages():
        nvidia_dir = os.path.join(sp, "nvidia")
        if not os.path.isdir(nvidia_dir):
            continue
        for pkg in os.listdir(nvidia_dir):
            bin_dir = os.path.join(nvidia_dir, pkg, "bin")
            if os.path.isdir(bin_dir):
                os.add_dll_directory(bin_dir)
                os.environ["PATH"] = bin_dir + os.pathsep + os.environ["PATH"]


register_cuda_dlls()


def auto_device():
    """有可用 CUDA 显卡则返回 (cuda, float16)，否则 (cpu, int8)。"""
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"


def fmt(t):
    t = int(float(t))
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def main():
    ap = argparse.ArgumentParser(description="faster-whisper 音频转写")
    ap.add_argument("audio", help="音频文件路径")
    ap.add_argument("-o", "--output", required=True, help="输出 md 路径")
    ap.add_argument("--model", default="small",
                    help="模型：tiny / base / small / medium / large-v3（默认 small）")
    ap.add_argument("--device", default=None,
                    help="cpu 或 cuda（默认自动检测：有 N 卡用 cuda，否则 cpu）")
    ap.add_argument("--compute", default=None,
                    help="int8 / float16 / float32（默认随设备：cuda→float16，cpu→int8）")
    ap.add_argument("--title", default="语音转写", help="写入文件头的标题")
    ap.add_argument("--lang", default=None,
                    help="语音语言代码（如 zh / ja / en），默认自动检测")
    args = ap.parse_args()

    if not os.path.exists(args.audio):
        sys.exit(f"错误：音频不存在：{args.audio}")

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("错误：未安装 faster-whisper，请用 whisper-venv 的 python 运行本脚本")

    device, compute = auto_device()
    device = args.device or device
    compute = args.compute or compute

    print(f"加载模型 {args.model}（{device}/{compute}），首次会自动下载……",
          file=sys.stderr)
    model = WhisperModel(args.model, device=device, compute_type=compute)
    segments, info = model.transcribe(args.audio, language=args.lang, vad_filter=True)

    lines = [f"# {args.title}", "",
             f"- 来源: whisper 本地转写（{args.model}）",
             f"- 识别语言: {info.language}（置信度 {info.language_probability:.2f}）", ""]
    n = 0
    for seg in segments:
        text = seg.text.strip()
        if text:
            lines.append(f"[{fmt(seg.start)}] {text}")
            n += 1
    if n == 0:
        sys.exit("错误：转写结果为空（音频可能无声）")

    with open(args.output, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"共 {n} 段", file=sys.stderr)
    print(f"TRANSCRIPT={args.output}")


if __name__ == "__main__":
    main()
