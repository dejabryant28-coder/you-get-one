#!/usr/bin/env python3
"""
watch.py — extract scene-aware frames + a timestamped transcript from a video.

This is the workhorse behind the `claude-watch` skill. It does the mechanical
part (download, frame selection, transcription) and leaves the *understanding*
to Claude, which reads the extracted frames as images and writes the notes.

Pipeline:
  1. Acquire the video (local path, or download with yt-dlp).
  2. Detect scene changes with ffmpeg, then add "coverage-floor" frames across
     long static gaps so a single slide held for 5 minutes still gets sampled.
  3. Pull a transcript: captions first (free), Whisper API only as a fallback.
  4. Extract the chosen frames as JPEGs and write a manifest.json.
  5. Save everything under ~/claude-watch/library/<slug>/ (cache-aware).

Output is a directory the skill can hand straight to Claude. Nothing here calls
an LLM to summarize — that's the skill's job.

Adapted from the open-source claude-watch skill by Devini Labs
(https://github.com/devinilabs/claude-watch), MIT licensed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #

def log(msg: str) -> None:
    print(f"[claude-watch] {msg}", file=sys.stderr, flush=True)


def die(msg: str, code: int = 1) -> "NoReturn":  # type: ignore[name-defined]
    log(f"ERROR: {msg}")
    sys.exit(code)


def have(binary: str) -> bool:
    return shutil.which(binary) is not None


def run(cmd: list[str], capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE,
        text=True,
    )


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:60] or "video"


def fmt_ts(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:d}:{s:02d}"


# --------------------------------------------------------------------------- #
# video acquisition
# --------------------------------------------------------------------------- #

def source_slug(source: str) -> str:
    """Stable slug + cache key for a URL or local path."""
    if re.match(r"^https?://", source):
        parsed = urllib.parse.urlparse(source)
        qs = urllib.parse.parse_qs(parsed.query)
        vid = qs.get("v", [""])[0]
        if not vid and "youtu.be" in parsed.netloc:
            vid = parsed.path.strip("/")
        base = vid or Path(parsed.path).stem or parsed.netloc
        return slugify(base)
    return slugify(Path(source).stem)


def acquire_video(source: str, work: Path) -> tuple[Path, dict]:
    """Return (local_video_path, metadata). Downloads via yt-dlp if a URL."""
    meta: dict = {"source": source}

    if not re.match(r"^https?://", source):
        p = Path(source).expanduser().resolve()
        if not p.exists():
            die(f"local file not found: {p}")
        meta["title"] = p.stem
        return p, meta

    if not have("yt-dlp"):
        die("yt-dlp is required to download URLs. Install it "
            "(pip install yt-dlp) or pass a local file path.")

    out_tmpl = str(work / "video.%(ext)s")
    log(f"downloading {source} ...")
    # Prefer a reasonable single-file mp4/webm; also grab subtitles for free.
    cmd = [
        "yt-dlp",
        "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
        "--merge-output-format", "mp4",
        "--write-sub", "--write-auto-sub",
        "--sub-lang", "en.*", "--sub-format", "vtt/srt/best",
        "--no-playlist",
        "--print-json",
        "-o", out_tmpl,
        source,
    ]
    proc = run(cmd)
    if proc.returncode != 0:
        die(f"yt-dlp failed:\n{proc.stderr.strip()[-1500:]}")

    # Last JSON line carries the metadata.
    for line in reversed((proc.stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                info = json.loads(line)
                meta["title"] = info.get("title") or info.get("id")
                meta["uploader"] = info.get("uploader")
                meta["duration"] = info.get("duration")
                break
            except json.JSONDecodeError:
                pass

    vids = sorted(work.glob("video.*"))
    vids = [v for v in vids if v.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov", ".m4v"}]
    if not vids:
        die("download produced no playable video file")
    return vids[0], meta


# --------------------------------------------------------------------------- #
# probing + frame selection
# --------------------------------------------------------------------------- #

def probe_duration(video: Path) -> float:
    if not have("ffprobe"):
        return 0.0
    proc = run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(video),
    ])
    try:
        return float((proc.stdout or "0").strip())
    except ValueError:
        return 0.0


def scene_timestamps(video: Path, threshold: float,
                     start: float, end: float) -> list[float]:
    """Timestamps (seconds) where ffmpeg detects a scene change."""
    log(f"detecting scene changes (threshold={threshold}) ...")
    vf = f"select='gt(scene,{threshold})',showinfo"
    proc = run([
        "ffmpeg", "-hide_banner", "-nostats",
        "-i", str(video),
        "-filter:v", vf,
        "-f", "null", "-",
    ])
    times: list[float] = []
    for m in re.finditer(r"pts_time:([0-9.]+)", proc.stderr or ""):
        t = float(m.group(1))
        if start <= t <= end:
            times.append(t)
    return sorted(set(round(t, 2) for t in times))


def coverage_floor(scene_ts: list[float], start: float, end: float,
                   max_gap: float) -> list[float]:
    """Insert frames so no stretch longer than max_gap goes unsampled."""
    anchors = [start] + scene_ts + [end]
    extra: list[float] = []
    for a, b in zip(anchors, anchors[1:]):
        gap = b - a
        if gap > max_gap:
            n = int(gap // max_gap)
            step = gap / (n + 1)
            for i in range(1, n + 1):
                extra.append(round(a + i * step, 2))
    return extra


def budget_frames(times: list[float], max_frames: int) -> list[float]:
    """Evenly thin the list down to the frame budget, keeping endpoints."""
    times = sorted(set(times))
    if len(times) <= max_frames:
        return times
    step = len(times) / max_frames
    kept = [times[min(int(i * step), len(times) - 1)] for i in range(max_frames)]
    return sorted(set(kept))


def extract_frames(video: Path, times: list[float], frames_dir: Path,
                   resolution: int) -> list[dict]:
    frames_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    for i, t in enumerate(times):
        name = f"frame_{i:03d}_{int(t):06d}s.jpg"
        out = frames_dir / name
        proc = run([
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-ss", f"{t:.2f}", "-i", str(video),
            "-frames:v", "1",
            "-vf", f"scale=-2:{resolution}",
            "-q:v", "3",
            str(out),
        ])
        if out.exists():
            manifest.append({"file": name, "seconds": t, "timestamp": fmt_ts(t)})
        else:
            log(f"warn: could not extract frame at {fmt_ts(t)}: "
                f"{(proc.stderr or '').strip()[-200:]}")
    return manifest


# --------------------------------------------------------------------------- #
# transcript
# --------------------------------------------------------------------------- #

def parse_vtt(path: Path) -> list[dict]:
    """Parse WebVTT / SRT into [{seconds, timestamp, text}]."""
    def to_seconds(stamp: str) -> float:
        stamp = stamp.replace(",", ".").strip()
        parts = stamp.split(":")
        parts = [float(p) for p in parts]
        while len(parts) < 3:
            parts.insert(0, 0.0)
        h, m, s = parts[-3], parts[-2], parts[-1]
        return h * 3600 + m * 60 + s

    segments: list[dict] = []
    cur_start = None
    cur_text: list[str] = []
    line_re = re.compile(r"(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}|\d{1,2}:\d{2}[.,]\d{1,3})\s*-->\s*"
                         r"(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}|\d{1,2}:\d{2}[.,]\d{1,3})")
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        m = line_re.search(line)
        if m:
            if cur_start is not None and cur_text:
                segments.append({"seconds": cur_start, "text": " ".join(cur_text)})
            cur_start = to_seconds(m.group(1))
            cur_text = []
        elif line and not line.isdigit() and "WEBVTT" not in line and "-->" not in line:
            clean = re.sub(r"<[^>]+>", "", line)
            if clean:
                cur_text.append(clean)
    if cur_start is not None and cur_text:
        segments.append({"seconds": cur_start, "text": " ".join(cur_text)})

    # De-dupe consecutive identical lines (auto-captions repeat a lot).
    deduped: list[dict] = []
    for seg in segments:
        if deduped and deduped[-1]["text"] == seg["text"]:
            continue
        seg["timestamp"] = fmt_ts(seg["seconds"])
        deduped.append(seg)
    return deduped


def whisper_transcribe(video: Path, work: Path, provider: str,
                       start: float, end: float) -> list[dict]:
    """Transcribe via a Whisper-compatible API (Groq or OpenAI)."""
    try:
        import requests  # noqa: F401
    except ImportError:
        die("the 'requests' package is needed for Whisper fallback "
            "(pip install requests), or re-run with --no-whisper")
    import requests

    providers = {
        "groq": ("GROQ_API_KEY", "https://api.groq.com/openai/v1/audio/transcriptions",
                 "whisper-large-v3-turbo"),
        "openai": ("OPENAI_API_KEY", "https://api.openai.com/v1/audio/transcriptions",
                   "whisper-1"),
    }
    if provider not in providers:
        die(f"unknown whisper provider: {provider}")
    env_key, url, model = providers[provider]
    key = os.environ.get(env_key)
    if not key:
        die(f"{env_key} not set; export it or re-run with --no-whisper")

    audio = work / "audio.mp3"
    log("extracting audio for transcription ...")
    args = ["ffmpeg", "-hide_banner", "-nostats", "-y", "-i", str(video)]
    if start > 0:
        args += ["-ss", f"{start:.2f}"]
    if end and end > start:
        args += ["-to", f"{end:.2f}"]
    args += ["-ac", "1", "-ar", "16000", "-b:a", "64k", str(audio)]
    if run(args).returncode != 0 or not audio.exists():
        die("failed to extract audio for Whisper")

    log(f"transcribing with {provider} ({model}) ...")
    with open(audio, "rb") as fh:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {key}"},
            files={"file": (audio.name, fh, "audio/mpeg")},
            data={"model": model, "response_format": "verbose_json"},
            timeout=600,
        )
    if resp.status_code != 200:
        die(f"{provider} transcription failed ({resp.status_code}): {resp.text[:500]}")

    data = resp.json()
    offset = start if start > 0 else 0.0
    segs = []
    for s in data.get("segments", []):
        t = float(s.get("start", 0)) + offset
        text = (s.get("text") or "").strip()
        if text:
            segs.append({"seconds": round(t, 2), "timestamp": fmt_ts(t), "text": text})
    if not segs and data.get("text"):
        segs.append({"seconds": offset, "timestamp": fmt_ts(offset),
                     "text": data["text"].strip()})
    return segs


def get_transcript(video: Path, work: Path, args, start: float,
                   end: float) -> tuple[list[dict], str]:
    # 1) captions downloaded by yt-dlp, or a sibling .vtt/.srt for local files.
    candidates = list(work.glob("*.vtt")) + list(work.glob("*.srt"))
    if not candidates and not re.match(r"^https?://", args.source):
        p = Path(args.source).expanduser()
        candidates = list(p.parent.glob(p.stem + "*.vtt")) + \
            list(p.parent.glob(p.stem + "*.srt"))
    if candidates:
        # Prefer English if the language is in the filename.
        candidates.sort(key=lambda c: (0 if re.search(r"\.en", c.name) else 1, len(c.name)))
        segs = parse_vtt(candidates[0])
        if segs:
            segs = [s for s in segs if start <= s["seconds"] <= (end or 1e12)]
            log(f"using captions ({candidates[0].name}, {len(segs)} segments)")
            return segs, "captions"

    # 2) Whisper fallback.
    if args.no_whisper:
        log("no captions found and --no-whisper set; skipping transcript")
        return [], "none"
    env_key = {"groq": "GROQ_API_KEY", "openai": "OPENAI_API_KEY"}[args.whisper]
    if not os.environ.get(env_key):
        log(f"no captions and {env_key} not set; continuing without a transcript "
            f"(set {env_key} or use captions for spoken words)")
        return [], "none"
    segs = whisper_transcribe(video, work, args.whisper, start, end)
    return segs, f"whisper:{args.whisper}"


# --------------------------------------------------------------------------- #
# transcript rendering
# --------------------------------------------------------------------------- #

def write_transcript_md(segs: list[dict], path: Path) -> None:
    lines = ["# Transcript", ""]
    for s in segs:
        lines.append(f"- **[{s['timestamp']}]** {s['text']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# audio analysis
# --------------------------------------------------------------------------- #
#
# Claude cannot ingest raw audio — there is no audio input channel. What it CAN
# do is read images and text. So we turn sound into both: spectrogram + waveform
# images (which the model literally "sees") and a loudness timeline (which it
# reads as data). That is the closest an image+text model gets to hearing.

def extract_audio(video: Path, work: Path, start: float, end: float) -> Path | None:
    """Extract the windowed audio track to a mono wav for analysis."""
    audio = work / "audio_analysis.wav"
    args = ["ffmpeg", "-hide_banner", "-nostats", "-y"]
    if start > 0:
        args += ["-ss", f"{start:.2f}"]
    args += ["-i", str(video)]
    if end and end > start:
        args += ["-t", f"{end - start:.2f}"]
    args += ["-ac", "1", "-ar", "22050", "-vn", str(audio)]
    if run(args).returncode != 0 or not audio.exists() or audio.stat().st_size < 1024:
        return None
    return audio


def render_spectrogram(src: Path, out_png: Path, label: str) -> bool:
    vf = (f"showspectrumpic=s=1280x420:legend=1:scale=log:color=intensity,"
          f"drawtext=text='{label}':fontcolor=white:fontsize=16:x=10:y=6:"
          f"box=1:boxcolor=black@0.5")
    ok = run(["ffmpeg", "-hide_banner", "-nostats", "-y", "-i", str(src),
              "-lavfi", vf, str(out_png)]).returncode == 0
    # drawtext may be unavailable in minimal builds; retry without the label.
    if not (ok and out_png.exists()):
        ok = run(["ffmpeg", "-hide_banner", "-nostats", "-y", "-i", str(src),
                  "-lavfi", "showspectrumpic=s=1280x420:legend=1:scale=log:"
                  "color=intensity", str(out_png)]).returncode == 0
    return ok and out_png.exists()


def render_waveform(src: Path, out_png: Path) -> bool:
    ok = run(["ffmpeg", "-hide_banner", "-nostats", "-y", "-i", str(src),
              "-lavfi", "showwavespic=s=1280x240:colors=0x33ccff",
              str(out_png)]).returncode == 0
    return ok and out_png.exists()


def loudness_timeline(src: Path, work: Path, start_offset: float) -> list[dict]:
    """Momentary loudness (LUFS) over time, via ffmpeg's ebur128 filter.

    ebur128 only prints a summary to stderr; the per-frame values come from the
    ametadata filter, which we route to a file and then parse.
    """
    meta = work / "loudness.txt"
    run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src),
         "-af", f"ebur128=metadata=1,ametadata=mode=print:file={meta}",
         "-f", "null", "-"])
    if not meta.exists():
        return []
    points: list[dict] = []
    t = None
    for line in meta.read_text(errors="ignore").splitlines():
        mt = re.search(r"pts_time:([0-9.]+)", line)
        if mt:
            t = float(mt.group(1))
            continue
        mm = re.search(r"lavfi\.r128\.M=(-?[0-9.]+)", line)
        if mm and t is not None:
            lufs = float(mm.group(1))
            if lufs > -70:  # drop -120 silence/-inf sentinel readings
                points.append({"seconds": round(t + start_offset, 1), "lufs": lufs})
    return points


def summarize_loudness(points: list[dict]) -> dict:
    if not points:
        return {}
    vals = [p["lufs"] for p in points]
    avg = sum(vals) / len(vals)
    loud = max(points, key=lambda p: p["lufs"])
    quiet = min(points, key=lambda p: p["lufs"])
    # Sample the curve at ~12 evenly spaced points so notes can show a shape.
    n = len(points)
    idxs = sorted(set(int(i * (n - 1) / 11) for i in range(min(12, n))))
    curve = [{"timestamp": fmt_ts(points[i]["seconds"]),
              "lufs": round(points[i]["lufs"], 1)} for i in idxs]
    return {
        "average_lufs": round(avg, 1),
        "loudest": {"timestamp": fmt_ts(loud["seconds"]), "lufs": round(loud["lufs"], 1)},
        "quietest": {"timestamp": fmt_ts(quiet["seconds"]), "lufs": round(quiet["lufs"], 1)},
        "curve": curve,
    }


def write_audio_md(summary: dict, tiles: list[dict], path: Path) -> None:
    lines = ["# Audio", ""]
    if summary:
        lines += [
            f"- **Average loudness:** {summary['average_lufs']} LUFS",
            f"- **Loudest moment:** {summary['loudest']['lufs']} LUFS "
            f"at {summary['loudest']['timestamp']}",
            f"- **Quietest moment:** {summary['quietest']['lufs']} LUFS "
            f"at {summary['quietest']['timestamp']}",
            "",
            "## Loudness over time",
        ]
        for pt in summary.get("curve", []):
            lines.append(f"- [{pt['timestamp']}] {pt['lufs']} LUFS")
        lines.append("")
    lines.append("## Spectrogram / waveform images")
    for t in tiles:
        lines.append(f"- `{t['file']}` — {t['kind']} for {t['range']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze_audio(video: Path, work: Path, out: Path, start: float, end: float,
                  max_tiles: int) -> dict:
    """Produce spectrogram/waveform images + a loudness timeline."""
    audio = extract_audio(video, work, start, end)
    if audio is None:
        log("no analyzable audio track found; skipping audio layer")
        return {"available": False}

    adir = out / "audio"
    adir.mkdir(parents=True, exist_ok=True)
    tiles: list[dict] = []

    # Whole-window overview (time is compressed, good for spotting structure).
    if render_spectrogram(audio, adir / "spectrogram_full.png", "full"):
        tiles.append({"file": "audio/spectrogram_full.png", "kind": "spectrogram",
                      "range": f"{fmt_ts(start)}-{fmt_ts(end)}"})
    if render_waveform(audio, adir / "waveform_full.png"):
        tiles.append({"file": "audio/waveform_full.png", "kind": "waveform",
                      "range": f"{fmt_ts(start)}-{fmt_ts(end)}"})

    # Per-chunk detail spectrograms so fine structure isn't lost to compression.
    window = max(0.0, end - start)
    if window > 0 and max_tiles > 0:
        chunk = max(30.0, window / max_tiles)
        n = int(window // chunk) + (1 if window % chunk else 0)
        for i in range(min(n, max_tiles)):
            c0, c1 = i * chunk, min((i + 1) * chunk, window)
            slice_wav = work / f"chunk_{i:02d}.wav"
            run(["ffmpeg", "-hide_banner", "-nostats", "-y", "-ss", f"{c0:.2f}",
                 "-i", str(audio), "-t", f"{c1 - c0:.2f}", str(slice_wav)])
            if not slice_wav.exists():
                continue
            label = f"{fmt_ts(start + c0)}-{fmt_ts(start + c1)}"
            png = adir / f"spectrogram_{i:02d}.png"
            if render_spectrogram(slice_wav, png, label):
                tiles.append({"file": f"audio/spectrogram_{i:02d}.png",
                              "kind": "spectrogram", "range": label})

    summary = summarize_loudness(loudness_timeline(audio, work, start))
    if tiles or summary:
        write_audio_md(summary, tiles, out / "audio.md")
    log(f"audio: {len(tiles)} spectrogram/waveform image(s)"
        + (f", loudness avg {summary['average_lufs']} LUFS" if summary else ""))
    return {"available": bool(tiles or summary), "tiles": tiles,
            "loudness": summary, "file": "audio.md" if (tiles or summary) else None}


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="watch.py",
        description="Extract scene-aware frames + transcript from a video.",
    )
    p.add_argument("source", help="YouTube (or other) URL, or a local file path")
    p.add_argument("--topic", default="", help="optional focus/topic label")
    p.add_argument("--start", type=float, default=0.0, help="start second")
    p.add_argument("--end", type=float, default=0.0, help="end second (0 = to end)")
    p.add_argument("--max-frames", type=int, default=80, help="frame budget")
    p.add_argument("--resolution", type=int, default=720,
                   help="frame height in px (bump for tiny text)")
    p.add_argument("--scene-threshold", type=float, default=0.3,
                   help="scene-change sensitivity 0..1 (lower = more frames)")
    p.add_argument("--max-gap", type=float, default=45.0,
                   help="max seconds between sampled frames")
    p.add_argument("--whisper", choices=["groq", "openai"], default="groq",
                   help="Whisper provider used only when captions are missing")
    p.add_argument("--no-whisper", action="store_true",
                   help="never call a paid transcription API")
    p.add_argument("--no-audio", action="store_true",
                   help="skip the audio layer (spectrograms / waveform / loudness)")
    p.add_argument("--audio-tiles", type=int, default=8,
                   help="max per-chunk spectrogram images for audio detail")
    p.add_argument("--out-dir", default="",
                   help="override output dir (default: ~/claude-watch/library/<slug>)")
    p.add_argument("--force", action="store_true", help="ignore cache and rebuild")
    return p


def params_signature(args) -> str:
    keys = ["start", "end", "max_frames", "resolution", "scene_threshold",
            "max_gap", "whisper", "no_whisper", "no_audio", "audio_tiles"]
    blob = json.dumps({k: getattr(args, k) for k in keys}, sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()[:10]


def main() -> None:
    args = build_parser().parse_args()

    for b in ("ffmpeg", "ffprobe"):
        if not have(b):
            die(f"{b} not found on PATH. Install ffmpeg first.")

    slug = source_slug(args.source)
    if args.out_dir:
        out = Path(args.out_dir).expanduser().resolve()
    else:
        out = Path.home() / "claude-watch" / "library" / slug
    manifest_path = out / "manifest.json"

    sig = params_signature(args)
    if manifest_path.exists() and not args.force:
        try:
            existing = json.loads(manifest_path.read_text())
            if existing.get("signature") == sig:
                log(f"cache hit — reusing {out}")
                print(json.dumps({"cached": True, "out_dir": str(out),
                                  "manifest": str(manifest_path)}))
                return
        except json.JSONDecodeError:
            pass

    out.mkdir(parents=True, exist_ok=True)
    work = out / "_work"
    work.mkdir(exist_ok=True)

    video, meta = acquire_video(args.source, work)
    duration = meta.get("duration") or probe_duration(video)
    start = max(0.0, args.start)
    end = args.end if args.end and args.end > start else (duration or 1e12)
    if duration:
        end = min(end, duration)
    log(f"video: {meta.get('title', slug)}  duration={fmt_ts(duration) if duration else '?'}"
        f"  window=[{fmt_ts(start)}..{fmt_ts(end)}]")

    # ---- frame selection ----
    scenes = scene_timestamps(video, args.scene_threshold, start, end)
    floor = coverage_floor(scenes, start, end, args.max_gap)
    all_ts = sorted(set([start] + scenes + floor))
    all_ts = [t for t in all_ts if start <= t <= end]
    chosen = budget_frames(all_ts, args.max_frames)
    log(f"frames: {len(scenes)} scene-changes + {len(floor)} coverage "
        f"-> {len(chosen)} extracted (budget {args.max_frames})")
    frames = extract_frames(video, chosen, out / "frames", args.resolution)

    # ---- transcript ----
    segs, transcript_source = get_transcript(video, work, args, start, end)
    if segs:
        write_transcript_md(segs, out / "transcript.md")

    # ---- audio layer (spectrograms / waveform / loudness) ----
    if args.no_audio:
        audio_info = {"available": False}
    else:
        audio_info = analyze_audio(video, work, out, start, end, args.audio_tiles)

    # ---- manifest ----
    manifest = {
        "signature": sig,
        "source": args.source,
        "title": meta.get("title", slug),
        "uploader": meta.get("uploader"),
        "topic": args.topic,
        "duration_seconds": duration,
        "window": {"start": start, "end": end},
        "params": {
            "max_frames": args.max_frames, "resolution": args.resolution,
            "scene_threshold": args.scene_threshold, "max_gap": args.max_gap,
        },
        "frames": frames,
        "transcript": {
            "source": transcript_source,
            "segments": len(segs),
            "file": "transcript.md" if segs else None,
        },
        "audio": audio_info,
        "out_dir": str(out),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Clean up the (potentially large) working copy of the video/audio.
    shutil.rmtree(work, ignore_errors=True)

    log(f"done -> {out}")
    print(json.dumps({
        "cached": False,
        "out_dir": str(out),
        "manifest": str(manifest_path),
        "frames_dir": str(out / "frames"),
        "frame_count": len(frames),
        "transcript_file": str(out / "transcript.md") if segs else None,
        "transcript_source": transcript_source,
        "audio_available": audio_info.get("available", False),
        "audio_file": str(out / "audio.md") if audio_info.get("file") else None,
        "audio_dir": str(out / "audio") if audio_info.get("available") else None,
        "title": meta.get("title", slug),
    }))


if __name__ == "__main__":
    main()
