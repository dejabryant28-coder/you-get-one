---
name: claude-watch
description: >-
  Give Claude the ability to "watch" a video — picture AND sound — and turn it
  into structured study notes. Downloads the video (or reads a local file),
  samples scene-aware frames with ffmpeg, pulls a timestamped transcript
  (captions first, Whisper API fallback), and renders the audio track into
  spectrogram + waveform images plus a loudness timeline. Claude then reads the
  frames and the audio images and writes notes.md. Use when the user shares a
  tutorial/lecture/talk video URL or file and wants notes, a summary, key
  concepts, extracted code, a walkthrough, or a read on tone/energy/audio — e.g.
  "watch this video", "take notes on this lecture", "summarize this tutorial",
  "what's in this talk". Also does creator "review" breakdowns — reverse-engineer
  a video's hook, visuals, pacing, and structure and write a fresh script in the
  same shape — for "review this video", "break down this reel/short", "what makes
  this hook work", "reverse-engineer this". Best under ~30 min; use --start/--end
  for longer content.
---

# claude-watch

Turn any tutorial or lecture video into structured, timestamped study notes.
The heavy lifting (download, frame selection, transcription, audio rendering)
happens in `scripts/watch.py`; **you** — Claude — supply the understanding by
reading the extracted frames + audio images and writing the notes.

## How you actually "watch" (important)

You have image vision but **no audio input channel** — you cannot ingest raw
sound. This skill works around that by turning a video into things you *can*
perceive:

- **Picture → frame images** you read directly.
- **Speech → a text transcript** you read.
- **Sound → spectrogram + waveform images and a loudness timeline** — you *see*
  the audio's frequency/energy structure and *read* its loudness as data.

So when you describe the audio (music vs speech, energy, emphasis, pace,
silences), be honest that you are inferring it from a visual/numeric
representation, not from literally hearing it. Within that framing it is
genuinely informative — a spectrogram plainly shows music vs voice, build-ups,
drops, and silence; the loudness curve shows emphasis and pauses.

## When to use

The user gives you a video (a YouTube/other URL, or a local file path) and wants
to *learn from it* rather than just get a link: notes, a summary, key ideas,
code that appeared on screen, a step-by-step walkthrough, or visual feedback.

## Workflow

Run these steps in order. Everything after step 3 is your job as the model.

> **Where the scripts live:** they sit in this skill's own `scripts/` folder.
> The commands below show the project path (`.claude/skills/claude-watch/…`); if
> the skill is installed elsewhere (account upload, plugin), run the same scripts
> from this skill's directory instead.

### 1. Preflight (and self-install)

```bash
python3 .claude/skills/claude-watch/scripts/preflight.py
```

Read the JSON. If `ready` is `false` (e.g. `ffmpeg` missing), self-install the
tools — works in any project, no setup hook needed:

```bash
bash .claude/skills/claude-watch/scripts/bootstrap.sh
```

Then re-run preflight. `yt-dlp` is only needed for URLs. Whisper keys are only
needed when a video has no captions; captions are free and tried first, so
**don't** ask the user for API keys up front.

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
| `--whisper` | `groq` | `local` (free, faster-whisper), `groq`, or `openai`; groq/openai fall back to local if no key |
| `--whisper-model` | `base` | local model size: `tiny`/`base`/`small`/`medium` |
| `--no-whisper` | off | never transcribe — captions or nothing |
| `--no-audio` | off | skip the audio layer (spectrograms/waveform/loudness) |
| `--audio-tiles` | `8` | max per-chunk spectrogram images for audio detail |
| `--out-dir` | library | write somewhere specific instead of the library |
| `--force` | off | ignore the cache and rebuild |

### 3. Load frames, transcript, and audio into context

Read `manifest.json` in `out_dir` for the full inventory:

- **Frames** (`frames` array + `frames_dir`) — **read every frame image** with
  the Read tool so you can actually see what was on screen. Named
  `frame_NNN_SECONDSs.jpg`, each mapped to its timestamp.
- **Transcript** (`transcript.md`) — the spoken words, timestamped.
- **Audio** (`audio` block + `audio.md` + `audio/` dir, when
  `audio_available`) — **read the spectrogram and waveform images** (`audio/*.png`)
  and the loudness curve in `audio.md`. Use them to characterize the sound:
  speech vs music vs silence, energy/emphasis over time, pacing, and pauses.
  Anchor observations to the timestamps on the images and in the curve.

### 4. Write the output — pick a mode

Two output shapes; choose by what the user wants:

- **Study notes** (default) — to *learn the content* (tutorial/lecture/talk).
  Write `notes.md` from the template below.
- **Review** — to *reverse-engineer why a video works* and get a reusable
  structure + a fresh script (reels/shorts/creator/travel content). Triggers:
  "review", "break down this reel", "what makes the hook work",
  "reverse-engineer", "rewrite in the same structure". Follow
  [`references/review-template.md`](references/review-template.md) and write
  `review.md`. For this mode, extract with `--max-gap 7 --scene-threshold 0.2`
  so soft dissolves / fast cuts aren't missed.

Synthesize the frames + transcript (+ audio) into the chosen file inside
`out_dir`. Then report the path to the user and give a short spoken summary. Do
**not** just paste the transcript — the value is in your synthesis.

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

## Audio
<Read from the spectrogram/waveform images + loudness curve. e.g. mostly spoken
narration, background music from mm:ss–mm:ss, a loud emphasis at mm:ss, a long
pause at mm:ss. State that this is inferred from the audio's visual/numeric
representation, not from hearing it. Omit this section if --no-audio was used.>

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
  and the audio images and say so in the notes; offer to re-run with a Whisper
  key if the user wants the spoken words as text.
- **Audio is inferred, not heard.** Read the spectrogram/waveform and loudness
  curve, but never claim you "heard" anything — you are reading a visual/numeric
  rendering of the sound. It's reliable for music-vs-speech, energy, and
  silences; it is not a substitute for the transcript's actual words.
- **Respect the cache.** A `"cached": true` result means the frames/transcript
  already exist in `out_dir` — just read and (re)write notes.

---

Adapted from the open-source **claude-watch** skill by Devini Labs
(<https://github.com/devinilabs/claude-watch>), MIT licensed.
