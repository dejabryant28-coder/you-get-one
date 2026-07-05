# Full Website Audit — "You Get One" Content Hub (Mame Dee Travel World)

> Complete, exhaustive inventory of the website at https://mametravel-t85c5jzl.manus.space/
> Prepared so it can be pasted into Perplexity / ChatGPT / Claude to get ideas on how to
> improve, expand, or rebuild it "100% better," and to plan content-creation + marketing tooling.

---

## 0. TL;DR — What this website actually IS

This is **not** a public marketing website for a travel agency. It is a **private,
single-page "content operations dashboard"** that one person (the brand owner, "Mame Dee")
uses to run a social-media content series called **"You Get One"** — a *This or That* travel
game across Instagram, TikTok, and Pinterest.

The whole site is a **posting workflow tool**:
- It holds 20 pre-made "This or That" travel posts.
- For each post you can **download the image**, **copy the caption** (written differently per
  platform), and **copy the hashtags**.
- You tap **"Mark as posted"** to grey it out and remove it from your to-do view, so you can
  track what's been published.
- State is saved **only in your browser** (localStorage) — nothing is stored on a server.

So it is a **personal social-media scheduling / asset library**, disguised as a webpage.

---

## 1. Identity & Branding

| Element | Value |
|---|---|
| Brand name | **Mame Dee Travel World** (abbreviated **MDTW**) |
| Content series / product name | **You Get One** (also written "You Get ONE") |
| Live-site browser tab title | **Mame Dee Travel World HQ** |
| Repo/code browser tab title | **You Get One – Content Hub** |
| On-page eyebrow/tag text | `You Get One · MDTW` |
| Main headline (H1) | **This or That Content Hub** |
| Footer slogan | **Make the wonders travel · keep the jollof debate going** |
| Core content format | "This or That" / "You Get One" — pick between two travel options |
| Niche | Travel (bucket-list destinations, Black travel, food, adventure, luxury) |

---

## 2. Full Page Structure (top → bottom, every visible element)

### 2.1 Header
- Eyebrow text (letter-spaced, uppercase): **`You Get One · MDTW`**
- H1 headline: **`This or That Content Hub`**
- Intro paragraph:
  > "Download the image, copy the caption per platform, grab the hashtags. Tap "Mark as posted" to clear it from your view."

### 2.2 Toolbar (controls row)
- Counter: **`[N] of [Total] left to post`** (live count; total = 20)
- Button: **`Show posted (N)`** — toggles visibility of already-posted cards (label flips to `Hide posted (N)`)
- Button: **`Reset all`** — asks "Bring all posts back to the list?" and un-marks everything

### 2.3 Main grid ("wrap")
- Responsive card grid (auto-fills columns, min card width ~330px).
- One card per post (20 cards). Each card contains:
  - **Number badge** (1–20) in a gold circle, top-left over the image
  - **"Posted" badge** (teal) top-right — only shows once marked as posted
  - **Cover image** (the This/That graphic)
  - **Card title** (the matchup, e.g. "Bali or Maldives")
  - **Actions row:**
    - **`↓ Download`** button (gold) — downloads the image with a branded filename (e.g. `ygo_bali_maldives.png`)
    - **`✓ Mark as posted`** button (teal) — greys out the card, adds "Posted" badge → becomes **`Put back`** when posted
  - **Per-platform caption blocks**, each with its own **Copy** button:
    - **INSTAGRAM** — full caption
    - **TIKTOK** — shorter, punchier caption
    - **PINTEREST** — descriptive/SEO caption
    - **5 NICHE HASHTAGS** — the hashtag set (gold label)
  - Note: the platform "Copy" buttons copy **caption + blank line + hashtags** together; the hashtag block's own Copy button copies just the hashtags.
- **Empty state** (when all 20 are posted): **"All posted. Tap "Show posted" to bring them back."**

### 2.4 Footer
- **`Make the wonders travel · keep the jollof debate going`**

---

## 3. Design System (exact spec, for a rebuild)

**Fonts (Google Fonts):**
- Headings: **DM Serif Display** (400)
- Body: **Cormorant Garamond** (400/500/600)
- Base font size: 18px, serif throughout — a warm, editorial, "luxury travel magazine" feel.

**Color palette (CSS variables):**
| Token | Hex | Use |
|---|---|---|
| `--bg` | `#0f1418` | Page background (near-black, cool) |
| `--panel` | `#161d23` | Card background |
| `--line` | `#2a353d` | Borders/dividers |
| `--ink` | `#f4efe7` | Primary text (warm off-white) |
| `--muted` | `#9fb0ba` | Secondary text (muted blue-grey) |
| `--gold` | `#e8d0a8` | Accent — numbers, download button, hashtag label |
| `--accent` | `#7ec8c0` | Accent — teal; platform labels, "posted" badge, primary buttons |

**Visual style:** dark, moody, gold + teal luxury palette; rounded corners (cards 16px,
buttons 9–10px); posted cards fade to 45% opacity + partial grayscale.

---

## 4. Technical Stack & Architecture (exact)

- **Single static HTML file** (`index.html`, ~18.5 KB) — no build step, no framework.
- **All 20 posts are hardcoded** in one JavaScript array (`POSTS`) inside a `<script>` tag.
- **Vanilla JavaScript** (no React/Vue/jQuery). ~45 lines of DOM code renders the cards.
- **Google Fonts** loaded via `<link>` (only external dependency).
- **Images:** 20 local `.jpg` files in an `/img/` folder (~3.2 MB total).
- **State/persistence:** browser **localStorage** under key `ygo_posted_v1`. No backend, no
  database, no analytics, no accounts. "Posted" status lives only on the device you use.
- **Clipboard:** uses `navigator.clipboard` for copy buttons.
- **Download:** anchor tag with `download` attribute; served images are `.jpg` but download
  filenames are branded `.png` (`ygo_*`).
- **Hosting:** deployed on **manus.space** (a Manus AI generated-site host). `.nojekyll` file
  present (GitHub Pages compatible).
- **SEO/social:** ⚠️ No meta description, no Open Graph tags, no favicon, no analytics — it's
  private by design.

---

## 5. THE FULL CONTENT LIBRARY — all 20 posts, verbatim

> For each: number, card title, image, Instagram caption, TikTok caption, Pinterest caption,
> and the 5 hashtags. This is the complete editorial content of the site.

### Post 1 — Nigeria or Ghana (Detty December)
- **Image:** `img/ghana_nigeria.jpg` → downloads as `ygo_ghana_nigeria.png`
- **Instagram:** "You get ONE December. Lagos or Accra? / Twist: same flights sold out months early, same energy, two different vibes. And yes... we're finally settling the jollof debate in the comments. NG or GH"
- **TikTok:** "you get ONE detty december Lagos or Accra?? the jollof debate ends in the comments NG or GH"
- **Pinterest:** "Detty December in Nigeria or Ghana. Two very different December trips. Save this and pick your side."
- **Hashtags:** #dettydecember #visitghana #lagosvibes #afrobeatstravel #blacktravel

### Post 2 — Safari or Sahara
- **Image:** `img/safari_sahara.jpg` → `ygo_safari_sahara.png`
- **Instagram:** "You get ONE bucket list trip. Lions or dunes? / Twist: one wakes you at sunrise for the Big Five. One keeps you up for a sky full of stars."
- **TikTok:** "safari or sahara?? sunrise lions or a sky full of stars pick one"
- **Pinterest:** "East Africa safari or Sahara desert. Two unforgettable African adventures. Which is your dream?"
- **Hashtags:** #safariadventure #saharadesert #eastafricatravel #moroccotravel #bucketlisttravel

### Post 3 — The Alps or The Islands
- **Image:** `img/swiss.jpg` → `ygo_swiss.png`
- **Instagram:** "You get ONE trip. The Alps or the Islands? / Twist: one slows you down, one wakes you up. Which version of you needs to travel right now?"
- **TikTok:** "the alps or the islands? one slows you down, one wakes you up. which one are you today?"
- **Pinterest:** "Switzerland and Liechtenstein or Philippines and Hong Kong. Cool calm or warm chaos. Save and pick."
- **Hashtags:** #alpsadventure #switzerlandtravel #philippinestravel #islandlife #wheretonext

### Post 4 — Beach or City
- **Image:** `img/beachcity.jpg` → `ygo_beachcity.png`
- **Instagram:** "You get ONE. Do nothing, or do everything? / Twist: be honest about which one actually rests you."
- **TikTok:** "beach or city? the real twist: which one ACTUALLY rests you"
- **Pinterest:** "Beach trip or city trip. Which one truly recharges you?"
- **Hashtags:** #beachvacation #citybreak #slowtravel #traveltips #wanderlust

### Post 5 — Relax or Adventure
- **Image:** `img/relax_adventure.jpg` → `ygo_relax_adventure.png`
- **Instagram:** "You get ONE week off all year. Spa and silence, or adrenaline and sore muscles? / Twist: one you enjoy in the moment. One you brag about for years. Which do you actually need?"
- **TikTok:** "your ONLY week off relax vs adventure one feels good now, one becomes a story forever pick"
- **Pinterest:** "Relax or adventure. How would you spend your one big trip this year?"
- **Hashtags:** #relaxationtravel #adventuretravel #selfcaretravel #wheretonext #bucketlist

### Post 6 — Rafting or Zipline
- **Image:** `img/rafting_zipline.jpg` → `ygo_rafting_zipline.png`
- **Instagram:** "You get ONE adrenaline day. White water rafting, or flying down a zipline? / Twist: one is fear of falling. One is fear of the rapids. Which fear wins?"
- **TikTok:** "rafting or zipline?? fear of the rapids or fear of falling be honest"
- **Pinterest:** "White water rafting or ziplining. Which adventure would you pick?"
- **Hashtags:** #adventuretravel #whitewaterrafting #zipline #adrenalinejunkie #thingstodo

### Post 7 — Road Trip USA or Train Through Europe
- **Image:** `img/roadtrip_train.jpg` → `ygo_roadtrip_train.png`
- **Instagram:** "You get ONE epic journey. A USA road trip, or a train through Europe? / Twist: one is total freedom and gas station snacks. One is castles out the window and zero parking stress."
- **TikTok:** "USA road trip or euro train?? freedom & snacks or castles out the window"
- **Pinterest:** "American road trip or a scenic train through Europe. Which journey calls you?"
- **Hashtags:** #roadtrip #eurotrip #traintravel #usaroadtrip #slowtravel

### Post 8 — Eat in Bangkok or Mexico City
- **Image:** `img/food_bangkok_mexico.jpg` → `ygo_food_bangkok_mexico.png`
- **Instagram:** "You get ONE plate tonight. Bangkok or Mexico City? / Twist: pad thai and mango sticky rice... or street tacos and churros. You can only sit at one table."
- **TikTok:** "one plate, one city Bangkok or Mexico City?? pad thai & mango sticky rice OR tacos & churros"
- **Pinterest:** "Street food in Bangkok or Mexico City. Which plate would you pick?"
- **Hashtags:** #foodtravel #streetfood #bangkokfood #mexicocityfood #foodie

### Post 9 — Queenstown or Interlaken (Adventure Day)
- **Image:** `img/activities_qt_int.jpg` → `ygo_activities_qt_int.png`
- **Instagram:** "You get ONE adventure day. Queenstown or Interlaken? / Twist: skydive and bungee over a lake... or paraglide and canyon swing over the Alps. Same heartbeat, different country."
- **TikTok:** "adventure capital showdown Queenstown or Interlaken?? skydive+bungee or paraglide+canyon swing"
- **Pinterest:** "Queenstown New Zealand or Interlaken Switzerland. Which adventure day would you survive?"
- **Hashtags:** #adventuretravel #queenstown #interlaken #adrenaline #bucketlist

### Post 10 — 1 Business Class or 4 Economy
- **Image:** `img/flights.jpg` → `ygo_flights.png`
- **Instagram:** "You get ONE. Fly business class once, or take four economy trips? / Twist: comfort you won't forget, or stories you keep forever? Plus... in this game, they're both free."
- **TikTok:** "they're BOTH free one fancy flight or four trips?? comfort you won't forget or stories you keep forever"
- **Pinterest:** "If both were free, would you fly business class once or take four economy trips?"
- **Hashtags:** #businessclass #traveldreams #wheretonext #traveltips #aviation

### Post 11 — The Pyramids or Petra
- **Image:** `img/egypt_jordan.jpg` → `ygo_egypt_jordan.png`
- **Instagram:** "You get ONE ancient wonder. Pyramids or Petra? / Twist: both will give you chills. Only one fits this trip."
- **TikTok:** "the pyramids or petra?? both give you chills, you only get one"
- **Pinterest:** "Egypt pyramids or Jordan's Petra. Two ancient wonders. Which is your dream?"
- **Hashtags:** #egypttravel #petra #jordantravel #ancientwonders #bucketlisttravel

### Post 12 — Fire & Ice or The Fjords
- **Image:** `img/iceland_norway.jpg` → `ygo_iceland_norway.png`
- **Instagram:** "You get ONE northern adventure. Fire and ice or the fjords? / Twist: both chase the northern lights. Which landscape calls you?"
- **TikTok:** "iceland or norway? both chase the northern lights which one calls you"
- **Pinterest:** "Iceland or Norway. Two epic northern adventures."
- **Hashtags:** #icelandtravel #norwaytravel #northernlights #nordictravel #adventuretravel

### Post 13 — The Cape or The Medina
- **Image:** `img/capetown_marrakech.jpg` → `ygo_capetown_marrakech.png`
- **Instagram:** "You get ONE African escape. The Cape or the Medina? / Twist: one is mountains and wine. One is souks and spice."
- **TikTok:** "cape town or marrakech? mountains & wine or souks & spice"
- **Pinterest:** "Cape Town or Marrakech. Two stunning sides of Africa. Where would you wander?"
- **Hashtags:** #capetown #marrakech #southafricatravel #moroccotravel #africatravel

### Post 14 — Tokyo or Seoul
- **Image:** `img/tokyo_seoul.jpg` → `ygo_tokyo_seoul.png`
- **Instagram:** "You get ONE Asia trip. Neon nights or cool and trendy? / Twist: one is sushi and shrines. One is kbbq and skincare hauls."
- **TikTok:** "tokyo or seoul?? sushi & shrines or kbbq & kpop pick your flight"
- **Pinterest:** "Tokyo or Seoul. Two incredible Asia city trips. Which would you book?"
- **Hashtags:** #tokyotravel #seoultravel #japantrip #koreatravel #asiatravel

### Post 15 — Santorini or Amalfi
- **Image:** `img/santorini_amalfi.jpg` → `ygo_santorini_amalfi.png`
- **Instagram:** "You get ONE Mediterranean summer. Blue domes or the cliff coast? / Twist: same sunsets, very different postcard."
- **TikTok:** "santorini or amalfi?? same sunsets, different postcard"
- **Pinterest:** "Santorini or the Amalfi Coast. Two dreamy Mediterranean escapes."
- **Hashtags:** #santorini #amalficoast #greecetravel #italytravel #mediterraneansummer

### Post 16 — Bali or Maldives
- **Image:** `img/bali_maldives.jpg` → `ygo_bali_maldives.png`
- **Instagram:** "You get ONE island trip. Jungle or overwater? / Twist: one is temples and rice fields. One is pure blue and total silence."
- **TikTok:** "bali or maldives?? temples & rice fields or pure blue silence"
- **Pinterest:** "Bali or Maldives. Two dream island escapes. Save and pick yours."
- **Hashtags:** #balitravel #maldives #islandlife #honeymoondestination #tropicaltravel

### Post 17 — Epcot or Hong Kong Disneyland
- **Image:** `img/epcot.jpg` → `ygo_epcot.png`
- **Instagram:** "You get ONE. Same mouse, different magic. / Twist: one you know by heart, one has rides the US will never get."
- **TikTok:** "same mouse, different magic Epcot or Hong Kong Disney? twist in the comments"
- **Pinterest:** "Epcot or Hong Kong Disneyland. Two totally different Disney days. Pick yours."
- **Hashtags:** #disneytravel #disneyparks #epcot #hongkongdisneyland #disneyworld

### Post 18 — Collect the World or Belong Somewhere
- **Image:** `img/tough_repeat.jpg` → `ygo_tough_repeat.png`
- **Instagram:** "You get ONE year of travel. A new country every trip but you can NEVER repeat one... or live in a single dream city abroad the whole year. / Twist: collect the world, or actually belong somewhere?"
- **TikTok:** "pick ONE for a year a new country every time but never repeat, OR live in one dream city abroad harder than it looks"
- **Pinterest:** "A new country every trip with no repeats, or living abroad in one city for a year. Which life?"
- **Hashtags:** #slowtravel #digitalnomad #expatlife #liveabroad #wheretonext

### Post 19 — Free Mystery Trip or Pay for Your Dream
- **Image:** `img/tough_mystery.jpg` → `ygo_tough_mystery.png`
- **Instagram:** "You get ONE trip. It's FREE but you don't get to choose where... or you pay full price for your exact dream trip. / Twist: would you give up control to travel for free?"
- **TikTok:** "free trip but you DON'T pick where or pay full for your dream trip what are you choosing??"
- **Pinterest:** "A free mystery trip you can't choose, or paying full for your dream destination. Which?"
- **Hashtags:** #mysterytrip #traveldeals #traveldreams #wheretonext #wanderlust

### Post 20 — One Luxury Trip or a Year of Weekends
- **Image:** `img/tough_luxury.jpg` → `ygo_tough_luxury.png`
- **Instagram:** "You get 10k for travel. One incredible luxury trip, or a whole year of weekend getaways? / Twist: one unforgettable week, or 20 little escapes you'll always remember?"
- **TikTok:** "10k to travel ONE luxury trip or a whole YEAR of weekend escapes?? pick"
- **Pinterest:** "One luxury trip or a year of weekend getaways for the same budget. How would you spend it?"
- **Hashtags:** #travelbudget #weekendgetaway #luxurytravel #traveltips #wheretonext

---

## 6. Content Patterns / "Formula" the series follows

- **Hook template:** every Instagram caption opens with **"You get ONE ..."** then a binary choice.
- **The "Twist":** every post adds a *twist line* that reframes the choice emotionally
  ("which one ACTUALLY rests you", "collect the world or belong somewhere").
- **Comment-bait:** several explicitly push people to argue in comments (the jollof debate).
- **Platform voice differs on purpose:**
  - Instagram = fuller, emotional, storytelling.
  - TikTok = lowercase, fast, punchy, chaotic energy.
  - Pinterest = descriptive + keyword-rich (SEO/"Save this").
- **Hashtags:** exactly 5 per post, niche-specific (not generic #travel spam).
- **Categories covered:** African travel (Detty December, safari, Cape Town/Marrakech,
  Ghana/Nigeria), Europe (Alps, Santorini/Amalfi, Iceland/Norway, Euro train), Asia
  (Tokyo/Seoul, Bali, Bangkok), adventure (rafting, zipline, Queenstown/Interlaken),
  aspirational/"hard choice" dilemmas (business vs economy, luxury vs weekends, mystery trip),
  food, Disney parks, ancient wonders.
- **Audience signal:** strong Black-travel / Afro-diaspora lean (Detty December, jollof,
  Afrobeats, #blacktravel) mixed with mainstream bucket-list travel.

---

## 7. What's Missing / Weaknesses (honest gaps for the "make it 100% better" prompt)

**As a workflow tool:**
- No backend — "posted" status is trapped in one browser; switch devices and it's gone.
- No scheduling / calendar / auto-posting — you still copy-paste manually into each app.
- No place to store the *actual posted date*, performance, or which platform you posted to.
- No way to add new posts without editing raw HTML/JS by hand.
- Images download as `.png` but are actually `.jpg` (filename/extension mismatch).
- No captions for YouTube Shorts, Facebook, Threads, or X/Twitter.
- No first-comment text, no CTA/link-in-bio copy, no Reel/TikTok audio suggestions.

**As a public brand asset (if that's ever the goal):**
- No SEO (no meta description, Open Graph, favicon, sitemap).
- No email capture, no booking/affiliate links, no monetization path.
- No "about," no contact, no way for a viewer to actually book travel.
- Not mobile-app installable (no PWA manifest).

---

## 8. Ideas to explore in your Perplexity/ChatGPT prompt

Consider asking the AI to help with any of these (this site is a great foundation):
1. **Rebuild as a real content OS** — add a backend/database (Notion, Airtable, Google
   Sheets, or Supabase) so posts, status, dates, and performance sync across devices.
2. **Add auto-scheduling** — connect to Buffer, Later, Metricool, Publer, or Meta/TikTok
   APIs so "Mark as posted" becomes "Schedule/Post."
3. **Generate more posts at scale** — use AI to expand the 20-post formula into 100+, and
   add captions for YouTube Shorts, Facebook, Threads, and X.
4. **Auto-generate the images** — use an image tool to produce the This/That graphics on brand.
5. **Turn it into a public quiz/lead magnet** — let followers actually vote/pick, capture
   emails, then funnel them toward booking travel (affiliate or agency).
6. **Analytics loop** — pull post performance back in to see which matchups win, and double
   down on those themes (Africa/Detty December looks like a strong pillar).
7. **Monetization** — affiliate links, a "book this trip" CTA, digital product (the content
   pack itself), or a paid content-calendar template.

---

## 9. Quick copy block (paste this line to give an AI the gist)

> "I have a private single-page web app (static HTML/JS, hosted on manus.space) that acts as
> a personal social-media content hub for my travel brand 'Mame Dee Travel World' / content
> series 'You Get One.' It holds 20 'This or That' travel posts; each has an image download,
> and separate Instagram, TikTok, and Pinterest captions plus 5 hashtags, with a 'mark as
> posted' tracker saved in browser localStorage. There's no backend, no scheduling, no
> analytics, no monetization. Help me recreate it 100% better and recommend content-creation
> and marketing apps/tools to plug in."
