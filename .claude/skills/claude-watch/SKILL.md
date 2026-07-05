---
name: claude-watch
description: >-
  Give Claude the ability to "watch" a video and turn it into structured study
  notes. Downloads the video (or reads a local file), samples scene-aware frames
  with ffmpeg, pulls a timestamped transcript (captions first, Whisper API only
  as a fallback), then Claude reads the frames as images and writes notes.md.
  Use when the user shares a tutorial/lecture/talk video URL or file and wants
  notes, a summary, key concepts, extracted code, or a walkthrough — e.g.
  "watch this video", "take notes on this lecture", "summarize this tutorial",
  "what's in this talk". Best for videos under ~30 min; use --start/--end for
  longer content.
---

# claude-watch

Turn any tutorial or lecture video into structured, timestamped study notes.
The heavy lifting (download, frame selection, transcription) happens in
`scripts/watch.py`; **you** — Claude — supply the understanding by reading the
extracted frames and writing the notes.

## When to use

The user gives you a video (a YouTube/other URL, or a local file path) and wants
to *learn from it* rather than just get a link: notes, a summary, key ideas,
code that appeared on screen, a step-by-step walkthrough, or visual feedback.

## Workflow

Run these steps in order. Everything after step 3 is your job as the model.

### 1. Preflight

```bash
python3 .claude/skills/claude-watch/scripts/preflight.py
```

Read the JSON. `ffmpeg`/`ffprobe` are required — if missing, tell the user how
to install them (the hints array explains). `yt-dlp` is only needed for URLs.
Whisper keys are only needed when a video has no captions; captions are free and
tried first, so **don't** ask the user for API keys up front.

### 2. Run the extractor

```bash
python3 .claude/skills/claude-watch/scripts/watch.py "<url-or-path>" [--topic "<focus>"] [flags]
```

The script prints a JSON line with `out_dir`, `frames_dir`, `frame_count`,
`transcript_file`, and `transcript_source`. It saves everything under
`~/claude-watch/library/<slug>/` and is **cache-aware** — re-running the same
source with the same flags returns instantly (`"cached": true`).

Useful flags (all optional):

| flag | default | when to use |
|------|---------|-------------|
| `--start` / `--end` | full video | focus on one section; **use for long videos** |
| `--max-frames` | `80` | raise for dense content, lower to save context |
| `--resolution` | `720` | raise to `1080` when on-screen text/code is tiny |
| `--scene-threshold` | `0.3` | lower (e.g. `0.2`) to catch more subtle cuts |
| `--max-gap` | `45` | max seconds between sampled frames on static slides |
| `--whisper` | `groq` | `groq` (cheap) or `openai`; only used if no captions |
| `--no-whisper` | off | never call a paid API — captions or nothing |
| `--out-dir` | library | write somewhere specific instead of the library |
| `--force` | off | ignore the cache and rebuild |

### 3. Load the frames into context

Read `manifest.json` in `out_dir` for the frame list (each has `file`,
`seconds`, `timestamp`). **Read every frame image** in `frames_dir` with the
Read tool so you can actually see what was on screen, and read `transcript.md`
for the spoken words. The frames are named `frame_NNN_SECONDSs.jpg` and the
manifest maps each to its timestamp.

### 4. Write the notes

Synthesize the frames + transcript into `notes.md` inside `out_dir`, following
the template below. Then report the path to the user and give a short spoken
summary. Do **not** just paste the transcript — the value is in your synthesis.

## notes.md template

```markdown
# <Title>

> Source: <url or filename> · Duration: <mm:ss> · Notes by claude-watch

## TL;DR
<3–4 sentence synthesis of what the video teaches and who it's for.>

## Key concepts
- **<Concept>** — <one line> _(<timestamp>)_
- ...

## Walkthrough
### <Section title> _(<start>–<end>)_
- **On screen:** <what the frame shows — UI, slide, diagram, code>
- **Said:** <the point being made, from the transcript>
- **Synthesis:** <your explanation / why it matters / what to remember>

<Repeat per meaningful section. Group frames; don't narrate every single one.>

## Code & commands
```<lang>
<any code or commands shown on screen, transcribed accurately from the frames>
```

## Diagrams & visuals
- <describe any diagram/architecture/flow shown, with timestamp>

## Open questions
- <things the video left unclear or that warrant follow-up>
```

## Guidance

- **Read the frames as images.** OCR the code and slide text yourself from the
  frames — the transcript won't contain what was only shown, not spoken.
- **Timestamps everywhere.** Anchor concepts and code to `mm:ss` so the user can
  jump back to the source.
- **Long videos:** if the video is much longer than ~30 minutes, suggest (or
  use) `--start`/`--end` to focus on the relevant section rather than blowing
  the frame budget across the whole thing.
- **Missing transcript:** if `transcript_source` is `none`, work from the frames
  alone and say so in the notes; offer to re-run with a Whisper key if the user
  wants the spoken track.
- **Respect the cache.** A `"cached": true` result means the frames/transcript
  already exist in `out_dir` — just read and (re)write notes.

---

Adapted from the open-source **claude-watch** skill by Devini Labs
(<https://github.com/devinilabs/claude-watch>), MIT licensed.
