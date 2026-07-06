# claude-watch

A [Claude Code skill](https://code.claude.com/docs/en/skills) that gives Claude
the ability to **watch a video and turn it into structured study notes**.

Point it at a tutorial, lecture, or talk (a URL or a local file) and it:

1. **Downloads** the video with `yt-dlp` (or reads your local file).
2. **Samples scene-aware frames** with `ffmpeg` — it detects scene changes and
   then fills long static gaps with "coverage-floor" frames, so a slide held for
   five minutes still gets sampled instead of producing a single frame.
3. **Pulls a timestamped transcript** — captions first (free), then **local
   Whisper** (`faster-whisper`, free, no key), then a hosted Whisper API
   (Groq/OpenAI) if you've set a key.
4. **Renders the audio** into spectrogram + waveform images and a loudness
   timeline (see "Watching with sound" below).
5. Hands the frames + transcript + audio images to **Claude**, which reads every
   frame as an image, OCRs the on-screen code/slides, characterizes the sound,
   and writes `notes.md` from a strict template (TL;DR, key concepts, timestamped
   walkthrough, extracted code, diagrams, audio, open questions).

Everything is saved under `~/claude-watch/library/<slug>/` and is cache-aware:
re-running the same source with the same flags is instant.

## Watching with sound

Claude has image vision but **no audio input** — it can't ingest raw sound. So
the skill converts sound into things Claude *can* perceive:

- **Spectrogram images** (`audio/spectrogram_*.png`) — Claude literally *sees*
  the frequency-vs-time structure: speech vs music vs silence, build-ups, drops.
- **A waveform image** (`audio/waveform_full.png`) — amplitude and pauses.
- **A loudness timeline** (`audio.md`, LUFS via ffmpeg's `ebur128`) — Claude
  *reads* energy and emphasis over time as data.

This is "seeing + reading" the audio rather than hearing it — the honest ceiling
of an image+text model — but in practice it reliably distinguishes music from
speech, flags emphasis and silence, and anchors it all to timestamps. Skip it
with `--no-audio`.

## Usage

Once installed, just ask Claude in natural language:

> watch https://youtube.com/watch?v=… and take notes
> summarize this lecture, focus on the auth section
> what code is shown in ./screen-recording.mp4?

Or drive the extractor directly:

```bash
python3 .claude/skills/claude-watch/scripts/watch.py "<url-or-path>" \
  --topic "kubernetes networking" --start 120 --end 900 --resolution 1080
```

See the flag table in [`SKILL.md`](./SKILL.md) for the full set.

## Requirements

| tool | required? | install |
|------|-----------|---------|
| `ffmpeg` / `ffprobe` | **yes** | `brew install ffmpeg` · `apt-get install ffmpeg` |
| `yt-dlp` | for URLs | `pip install yt-dlp` |
| `faster-whisper` | for free local transcription when captions are missing | `pip install faster-whisper` |
| `requests` | for the hosted Whisper API path | `pip install requests` |
| `GROQ_API_KEY` or `OPENAI_API_KEY` | optional — only if you prefer the hosted API over local | export in your shell |

Transcription order: **captions → local Whisper → hosted API**. With
`faster-whisper` installed you get transcripts for caption-less videos free and
with no key; hosted APIs are used only if you set a key or pass `--whisper groq`
with a key present.

Run `python3 .claude/skills/claude-watch/scripts/preflight.py` to check your
environment.

## Notes / limits

- Best results on videos under ~30 minutes; use `--start`/`--end` to focus on a
  section of longer content.
- Frame budget defaults to 80 (`--max-frames`).
- Captions are free and always tried first; Whisper is only a fallback and can
  be disabled entirely with `--no-whisper`.

## Credit

Adapted from the open-source **claude-watch** skill by **Devini Labs**
(<https://github.com/devinilabs/claude-watch>), MIT licensed. This is an
independent re-implementation of the same idea; see [`LICENSE`](./LICENSE).
