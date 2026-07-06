# Review mode — reverse-engineer a video

Use this template when the goal is **creator analysis**: break down *why a video
works* and produce a reusable structure, rather than study notes on its content.
Ideal for short-form (Reels / TikTok / Shorts) and travel/social videos.

## Before you write

For this kind of content, tune the extraction so soft dissolves and fast cuts
aren't missed:

```
--max-gap 7 --scene-threshold 0.2 --max-frames 60
```

Then read **every frame**, the transcript, and the audio loudness curve. The
hook and pacing live in the first seconds and in the cut rhythm — look there
hardest.

## Output: `review.md`

```markdown
# Review — <title / handle>

> <platform> · <length> · <format: talking-head / voiceover-broll / text-on-screen / …>
> Reviewed by claude-watch

## Snapshot
<2–3 sentences: what this video is, who it's for, and the single thing it does best.>

## Hook
- **0–3s (the scroll-stopper):**
  - On screen: <first frame(s) — subject, motion, text overlay, color>
  - Said: <opening line from transcript>
  - Why it works / doesn't: <pattern interrupt? bold claim? visual intrigue?>
- **0–10s (the promise):** <what it sets up that makes you stay — the open loop>

## Structure / beats
| Time | Beat | On screen | Retention purpose |
|------|------|-----------|-------------------|
| 0:00 | Hook | … | stop the scroll |
| …    | …    | … | … |
<One row per beat. "Retention purpose" = why this beat exists in the edit.>

## Visual presentation
- **Shot types & framing:** <wide/close, b-roll, screen-record, piece-to-camera>
- **Text & graphics:** <overlay style, captions, title cards, numbering>
- **Transitions & pacing:** <cut style; rough cuts-per-minute; fast vs. breathe>
- **Aesthetic:** <color grade, mood, brand consistency across frames>

## Audio & pacing
<From the loudness curve + transcript: music vs voice, energy shape, where it
swells or drops, VO cadence, deliberate pauses. Note as inferred from the audio
rendering, not heard.>

## Retention mechanics
- <open loops, pattern interrupts, payoffs, callbacks, list/countdown structure>

## Call to action
<What it asks for and how — comment bait, follow, link, "part 2".>

## Steal this — reusable skeleton
1. <hook formula>
2. <beat 2 purpose>
3. …
<The structure abstracted so it can be reused on a different topic.>

## Fresh script (same structure, your topic)
<Write a new short script that follows the skeleton above, ready to shoot.
Match the beat count and pacing; swap in a placeholder topic if none was given.>
```

## Notes
- Keep timestamps on everything so beats map back to the source.
- The **skeleton + fresh script** is the deliverable creators actually want — the
  earlier sections justify it; don't skimp on these two.
- If there's no transcript (`transcript_source: none`), build from frames +
  audio and say so.
