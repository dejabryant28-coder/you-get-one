#!/usr/bin/env python3
"""
preflight.py — quick environment check for the claude-watch skill.

Reports which binaries and API keys are available so the skill knows whether
it can download URLs and whether Whisper transcription is possible. Exits 0 as
long as the hard requirement (ffmpeg) is present; a missing yt-dlp only matters
for URLs, and missing Whisper keys only matter when a video has no captions.
"""

from __future__ import annotations

import json
import os
import shutil
import sys


def main() -> None:
    report = {
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "ffprobe": bool(shutil.which("ffprobe")),
        "yt_dlp": bool(shutil.which("yt-dlp")),
        "groq_key": bool(os.environ.get("GROQ_API_KEY")),
        "openai_key": bool(os.environ.get("OPENAI_API_KEY")),
    }
    try:
        import requests  # noqa: F401
        report["requests"] = True
    except ImportError:
        report["requests"] = False

    hints = []
    if not report["ffmpeg"] or not report["ffprobe"]:
        hints.append("Install ffmpeg (macOS: `brew install ffmpeg`; "
                     "Debian/Ubuntu: `apt-get install ffmpeg`). Required.")
    if not report["yt_dlp"]:
        hints.append("Install yt-dlp (`pip install yt-dlp`) to handle URLs; "
                     "not needed for local files.")
    if not (report["groq_key"] or report["openai_key"]):
        hints.append("No Whisper key found. Captions are used when available "
                     "(free); set GROQ_API_KEY or OPENAI_API_KEY only if you "
                     "need transcription for videos without captions.")

    report["hints"] = hints
    report["ready"] = report["ffmpeg"] and report["ffprobe"]

    print(json.dumps(report, indent=2))
    sys.exit(0 if report["ready"] else 2)


if __name__ == "__main__":
    main()
