# Story Director mode — score a video before it ships

Use this template when the goal is a **quality gate**: not "what is this video"
(study notes) and not "why does this video work" (review), but **"is this video
good enough to post yet?"** It scores the cut on how it will make an audience
*feel* and *act*, then blocks anything that isn't ready.

Think creative director, not SEO analyst. SEO asks *will it be found*. Story
Director asks *will it be felt, remembered, and followed*. Both matter; this mode
owns the second question.

Best for short-form you're about to publish (Reels / TikTok / Shorts) and
travel/social content. Triggers: "score this video", "story director",
"is this ready to post", "grade my cut", "rate this before I post".

## Before you write

Score off the **actual cut**, never a written description. Extract the same way
review mode does so soft dissolves and fast cuts aren't missed:

```
--max-gap 7 --scene-threshold 0.2 --max-frames 60
```

Then read **every frame**, the transcript, and the audio loudness curve. Two
dimensions live almost entirely in the opening and the cut rhythm — the
**first-3-seconds** score and the **ending** score — so look hardest there.

## The rubric

Score each dimension **1–10**. Be a tough grader: 8 is the *floor* for "ready",
not the average. A 6 is not "pretty good", it's "not good enough to post."

| Dimension | 1–10 | The question it answers |
|-----------|------|-------------------------|
| **Curiosity** | | Does the open loop make me *need* to know what's next? |
| **Emotional pull** | | Do I feel something — wonder, longing, tension, joy? |
| **Surprise** | | Is there a moment I didn't see coming? |
| **Memorability** | | Will I remember one specific image or line tomorrow? |
| **Shareability** | | Would I send this to one specific person, and who? |
| **Follow potential** | | Does it make me want *more from this creator*, not just this clip? |

Plus two pass/fail-weighted checks scored the same 1–10:

- **First-3-second retention** — from frames `0–3s` + the opening line + the
  audio's opening energy: would a scrolling thumb stop here? This is the single
  highest-leverage number on the card.
- **Ending earns the follow** — does the last beat pay off the promise and give a
  reason to hit follow (payoff, callback, cliffhanger, "part 2"), or does it just
  trail off?

## The gate (the whole point)

**Any dimension below 8 blocks the video.** For every sub-8 score you MUST:

1. Name the exact moment (timestamp) that costs the points.
2. Explain *why* it underperforms — in feeling terms, not jargon.
3. Give a concrete, shootable/editable fix, not "make it punchier."

Only when every dimension is 8+ (or the user overrides) is the verdict **SHIP**.
Otherwise the verdict is **NOT YET** and the fixes above are the deliverable.

Do not round up to be nice. A soft 8 that should be a 6 defeats the entire
purpose of the gate — the user is trusting the score to protect their feed.

## Output: `score.md`

```markdown
# Story Director score — <title / handle>

> <platform> · <length> · <format> · Scored by claude-watch
> Verdict: **SHIP** / **NOT YET**  ·  Lowest score: <dimension> (<n>)

## Scorecard
| Dimension | Score | One-line reason |
|-----------|:-----:|-----------------|
| Curiosity | n/10 | … |
| Emotional pull | n/10 | … |
| Surprise | n/10 | … |
| Memorability | n/10 | … |
| Shareability | n/10 | … |
| Follow potential | n/10 | … |
| First-3s retention | n/10 | … |
| Ending earns follow | n/10 | … |

**Feels like:** <one honest sentence on the emotional experience of watching it.>

## What's blocking (every score below 8)
### <Dimension> — <n>/10
- **Costs points at:** <mm:ss> — <what happens on screen / in the audio there>
- **Why it underperforms:** <in feeling terms — what the audience does or doesn't feel>
- **Fix:** <specific, shootable or editable change>

<Repeat for each sub-8 dimension. If nothing is below 8, write "Nothing blocking — clear to ship.">

## Keep (don't touch these in the edit)
- <the 1–3 things already working that a re-edit could accidentally break>

## If you only change one thing
<The single highest-leverage fix — usually first-3s or the ending — and why it
lifts the most scores at once.>
```

## Notes

- **The gate is the product.** The scorecard justifies the verdict; the "what's
  blocking" fixes are what the creator acts on. Don't skimp on the fixes.
- **Score the feeling, not the format.** "Cuts every 1.2s" is a review-mode
  observation. "The fast cuts never let me *land* on the reveal, so the payoff
  doesn't hit" is a Story Director observation. Stay on the second kind.
- **First-3s and ending carry the follow.** When a video is close but not ready,
  these two are almost always where the points are. Weight your attention there.
- **Audio is inferred, not heard.** As everywhere in claude-watch, read the
  spectrogram/loudness curve — never claim you heard it — but do use the energy
  shape to judge emotional pull and where the ending lands.
- **No transcript?** If `transcript_source: none`, score from frames + audio and
  say so; curiosity and surprise get harder to read without the words.
- Pairs well with **review mode**: run review to understand *why it works*, then
  Story Director to decide *whether it's ready*. Review explains, Story Director
  decides.
