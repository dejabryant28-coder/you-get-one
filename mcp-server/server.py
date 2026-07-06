#!/usr/bin/env python3
"""
claude-watch MCP server.

Exposes the claude-watch pipeline as MCP tools so it can be used as a
connector/integration — in Claude chat, Cowork, Claude Desktop, or any MCP
client — not just as a Claude Code skill.

Tools:
  - watch_video(source, ...)  -> extract frames + transcript + audio, return a
                                 structured breakdown (frame timestamps,
                                 transcript text, audio/loudness summary).
  - read_frames(out_dir, ...) -> return the extracted frames as image content so
                                 the model can actually SEE them.

The heavy lifting is delegated to the skill's watch.py, so behavior stays in one
place. The HOST running this server needs ffmpeg (+ yt-dlp for URLs,
faster-whisper for free local transcription).

Transport:
  - stdio (default) — for Claude Desktop / Claude Code local connectors.
  - streamable-http — set MCP_TRANSPORT=http to serve over HTTP for a remote
    connector (what claude.ai custom connectors require). Host it behind HTTPS.

Adapted from the MIT-licensed claude-watch skill by Devini Labs.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP, Image

REPO_ROOT = Path(__file__).resolve().parents[1]
WATCH = REPO_ROOT / ".claude" / "skills" / "claude-watch" / "scripts" / "watch.py"

# Bind host/port from env so the same file works locally and in a container
# (Railway/Render/Fly set $PORT). Only used for the http transport.
_HOST = os.environ.get("HOST", "0.0.0.0")
_PORT = int(os.environ.get("PORT", "8000"))
mcp = FastMCP("claude-watch", host=_HOST, port=_PORT)


def _last_json_line(text: str) -> dict:
    for line in reversed((text or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {}


@mcp.tool()
def watch_video(
    source: str,
    topic: str = "",
    start: float = 0.0,
    end: float = 0.0,
    max_frames: int = 60,
    max_gap: float = 15.0,
    scene_threshold: float = 0.3,
    resolution: int = 720,
    whisper: str = "local",
    no_audio: bool = False,
) -> dict:
    """Watch a video and return a structured breakdown.

    Downloads the video (URL) or reads a local file, samples scene-aware frames,
    pulls a timestamped transcript (captions -> local Whisper -> hosted API), and
    renders the audio to a loudness summary. Returns frame timestamps, the
    transcript, and the audio summary. Then call read_frames(out_dir) to load the
    frame images so you can describe what's on screen.

    Args:
        source: A video URL (YouTube/Instagram/Loom/…) or a local file path.
        topic: Optional focus label for the breakdown.
        start/end: Optional time window in seconds (end=0 means to the end).
        max_frames: Frame budget (default 60).
        max_gap: Max seconds between sampled frames — lower catches soft cuts.
        scene_threshold: Scene-change sensitivity 0..1 (lower = more frames).
        resolution: Frame height in px (raise for tiny on-screen text).
        whisper: 'local' (free, faster-whisper), 'groq', or 'openai'.
        no_audio: Skip the audio layer.

    Returns:
        dict with out_dir, title, duration, frames[], transcript, audio_summary.
    """
    if not WATCH.exists():
        return {"error": f"watch.py not found at {WATCH}"}

    cmd = [
        sys.executable, str(WATCH), source,
        "--max-frames", str(max_frames),
        "--max-gap", str(max_gap),
        "--scene-threshold", str(scene_threshold),
        "--resolution", str(resolution),
        "--whisper", whisper,
    ]
    if topic:
        cmd += ["--topic", topic]
    if start:
        cmd += ["--start", str(start)]
    if end:
        cmd += ["--end", str(end)]
    if no_audio:
        cmd += ["--no-audio"]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return {"error": "watch.py failed", "stderr": (proc.stderr or "")[-2000:]}

    result = _last_json_line(proc.stdout)
    out = Path(result.get("out_dir", ""))
    manifest = {}
    if (out / "manifest.json").exists():
        manifest = json.loads((out / "manifest.json").read_text())

    transcript = ""
    if (out / "transcript.md").exists():
        transcript = (out / "transcript.md").read_text()
    audio_summary = ""
    if (out / "audio.md").exists():
        audio_summary = (out / "audio.md").read_text()

    return {
        "out_dir": str(out),
        "title": manifest.get("title"),
        "duration_seconds": manifest.get("duration_seconds"),
        "transcript_source": result.get("transcript_source"),
        "frame_count": len(manifest.get("frames", [])),
        "frames": manifest.get("frames", []),
        "transcript": transcript,
        "audio_summary": audio_summary,
        "next_step": "Call read_frames(out_dir) to load the frame images, then "
                     "write the breakdown pairing each frame with the transcript "
                     "line at its timestamp.",
    }


@mcp.tool()
def read_frames(out_dir: str, indices: list[int] | None = None, limit: int = 12):
    """Return extracted frames as images so the model can see what's on screen.

    (Return type is intentionally unannotated: the frames come back as image
    content blocks, which FastMCP's structured-output schema can't model.)

    Args:
        out_dir: The out_dir returned by watch_video.
        indices: Specific frame indices (from the frames[] list) to load.
        limit: If indices is omitted, evenly sample up to this many frames.
    """
    out = Path(out_dir)
    manifest_path = out / "manifest.json"
    if not manifest_path.exists():
        raise ValueError(f"no manifest.json under {out_dir} — run watch_video first")
    frames = json.loads(manifest_path.read_text()).get("frames", [])
    if not frames:
        raise ValueError("no frames were extracted for this video")

    if indices:
        picked = [frames[i] for i in indices if 0 <= i < len(frames)]
    elif len(frames) <= limit:
        picked = frames
    else:
        step = len(frames) / limit
        picked = [frames[min(int(i * step), len(frames) - 1)] for i in range(limit)]

    images: list[Image] = []
    for fr in picked:
        p = out / "frames" / fr["file"]
        if p.exists():
            images.append(Image(path=str(p)))
    return images


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport in ("http", "streamable-http"):
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
