# Travel Photo Organizer (Composio + Google Drive)

Automatically sorts travel photos from your Samsung phone into a
location-based Google Drive folder structure:

```
Travel Photos/
├── _Inbox/                      ← your phone auto-uploads here
├── _Logs/photo-log.csv          ← run log (one row per photo)
├── Needs Review/
│   ├── No Location/             ← photos with no GPS data
│   └── Unclear Location/        ← GPS present but ambiguous
├── 2026/
│   ├── Ghana/Accra/July 2026/
│   ├── Nigeria/Lagos/July 2026/
│   └── Portugal/Lisbon/July 2026/
```

## Why the intake is a Drive folder (important!)

As of **March 31, 2025, the Google Photos API no longer lets any
third-party app read your photo library** — apps can only see photos
they themselves uploaded. On top of that, even before the shutdown the
Photos API stripped GPS location from downloads. So no Composio (or
Zapier/Make/n8n) automation can "watch Google Photos" for your camera
photos anymore.

The reliable, EXIF-preserving path is:

**Samsung phone → auto-upload to `Travel Photos/_Inbox` in Google Drive →
this automation sorts them.**

Set up the phone side once with a folder-sync app (e.g. *Autosync for
Google Drive* by MetaCtrl — free tier works):

1. Pair it with your Google account.
2. Sync pair: local folder `DCIM/Camera` → remote folder
   `Travel Photos/_Inbox`, mode **Upload only** (originals stay on the
   phone; nothing is ever deleted).
3. Do **not** add your Screenshots folder to the sync pair — this is your
   manual-approval gate for screenshots. (The script also skips any file
   whose name contains `screenshot` as a second line of defense.)

## What each run does (the exact workflow steps)

| # | Step | Composio tool |
|---|------|---------------|
| 1 | Find (or create once) the `Travel Photos` root + subfolders | `GOOGLEDRIVE_FIND_FILE`, `GOOGLEDRIVE_CREATE_FOLDER` |
| 2 | List new images in `_Inbox` with metadata (`md5Checksum`, `imageMediaMetadata.time/location`) | `GOOGLEDRIVE_FIND_FILE` |
| 3 | Skip already-processed files (by file ID) and duplicates (by MD5 hash) | local state + `_Logs/photo-log.csv` |
| 4 | Read date taken + GPS. Drive parses EXIF for you; if missing, download the file and parse EXIF locally (Pillow) | `GOOGLEDRIVE_DOWNLOAD_FILE` (fallback only) |
| 5 | Reverse-geocode GPS → city/country **offline** (`reverse_geocoder` package — coordinates never leave your machine) | — |
| 6 | Ensure `Travel Photos/<Year>/<Country>/<City>/<Month Year or Trip>` exists | `GOOGLEDRIVE_CREATE_FOLDER` |
| 7 | **Copy** the photo into the destination (original in `_Inbox` untouched) | `GOOGLEDRIVE_COPY_FILE_ADVANCED` |
| 8 | No GPS → `Needs Review/No Location`; ambiguous GPS (nearest known town > 50 km away) → `Needs Review/Unclear Location` | same as 6–7 |
| 9 | Append a row per photo to `_Logs/photo-log.csv` (file name, date taken, city, country, folder path, upload status, duplicate status) | `GOOGLEDRIVE_CREATE_FILE_FROM_TEXT` / `GOOGLEDRIVE_EDIT_FILE` |

## Required connected apps

| App | Needed? | Why |
|-----|---------|-----|
| **Google Drive** | ✅ the only required connection | read `_Inbox`, create folders, copy files, write the CSV log |
| Google Photos | ❌ | API can't see your camera photos anymore (see above) |
| Google Maps / geocoding APIs | ❌ | geocoding is done offline — better privacy, no extra account |
| Google Sheets | ❌ optional | only if you'd rather have the log as a Sheet instead of a CSV |

## Safest permission settings

Google's OAuth doesn't offer "one folder only" access, so the layers of
protection are:

1. **Code-level sandbox (always on):** every write this script performs
   starts from the `Travel Photos` folder ID. It never calls delete,
   rename, move, trash, or share endpoints at all — photos are only ever
   *copied*, and nothing is ever made public. Files created by Drive's
   API are **private by default**.
2. **Tightest OAuth scopes (recommended):** Composio's default managed
   Google Drive connector requests broad Drive scope. To narrow it,
   create a **custom auth config** in Composio (Auth Configs → Google
   Drive → use your own OAuth client) and request only:
   - `https://www.googleapis.com/auth/drive.readonly` — read the inbox
     photos your phone uploaded
   - `https://www.googleapis.com/auth/drive.file` — create/manage only
     the folders, copies, and log files this app itself creates
3. **Maximum isolation (optional):** use a dedicated Google account that
   contains only the `Travel Photos` folder, and point the phone sync at
   it. Then even full-Drive scope can't touch anything personal.

## Setup

```bash
cd travel-photo-organizer
pip install -r requirements.txt
cp config.example.json config.json     # then edit to taste
export COMPOSIO_API_KEY=...            # from https://platform.composio.dev
```

Connect Google Drive once (you will be shown a normal Google consent
screen listing the exact scopes — nothing connects without your click):
either from the Composio dashboard, or via the Composio SDK/MCP
`COMPOSIO_MANAGE_CONNECTIONS` for toolkit `googledrive`.

## Test run first (5 photos)

Test mode is **on by default** (`"test_mode": true` in config):

```bash
python organize_photos.py --dry-run   # step 0: prints the plan, writes NOTHING
python organize_photos.py --test      # step 1: processes exactly 5 photos
# check the folders + _Logs/photo-log.csv in Drive, then:
python organize_photos.py --limit 50  # step 2: a bigger batch
python organize_photos.py --full      # step 3: whole inbox
```

Set `"test_mode": false` in `config.json` when you're happy.

## Running it on a schedule

The script is idempotent (re-runs skip everything already processed), so
just run it on any schedule you like:

- **cron** (Linux/Mac): `0 * * * * cd .../travel-photo-organizer && python organize_photos.py`
- **Windows Task Scheduler**: same command, hourly.
- Or ask Claude to run it as a scheduled Routine from a cloud session.

## Config reference (`config.json`)

| Key | Default | Meaning |
|-----|---------|---------|
| `root_folder_name` | `Travel Photos` | the only Drive folder ever touched |
| `test_mode` / `max_photos_per_run` | `true` / `5` | safety limit until you disable it |
| `include_videos` | `false` | also organize videos (most lack GPS → Needs Review) |
| `skip_name_patterns` | `["screenshot", "-WA0"]` | never organize matching files (screenshots, WhatsApp media) |
| `unclear_location_km_threshold` | `50` | GPS farther than this from any known town → Unclear Location |
| `trips` | example entry | date ranges that use a trip name instead of "July 2026" as the leaf folder |

## Guarantees

- Originals in `_Inbox` are **never deleted, renamed, edited, or moved**.
- Nothing is **ever shared** — no sharing API is called anywhere.
- GPS coordinates are geocoded **offline** and never sent to third parties.
- Duplicates (identical content, by MD5) are detected and skipped.
- Every photo's outcome is recorded in `_Logs/photo-log.csv`.
