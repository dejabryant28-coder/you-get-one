# Travel Photo Organizer (Composio + OneDrive)

Automatically sorts travel photos from your Samsung phone into a
location-based OneDrive folder structure:

```
OneDrive/
├── Pictures/Samsung Gallery/DCIM/Camera   ← phone syncs here (READ-ONLY source)
└── Travel Photos/
    ├── _Logs/photo-log.csv                ← run log (one row per photo)
    ├── Needs Review/
    │   ├── No Location/                   ← photos with no GPS data
    │   └── Unclear Location/              ← GPS present but ambiguous
    └── 2026/
        ├── Ghana/           ← one folder per country (international)
        ├── Mexico/
        │   └── 20260511_143105 — Villa de Juárez — Viña de Liceaga.jpg
        ├── Egypt/
        └── California/      ← domestic photos group by state
            └── 20260607_… — Long Beach — Long Beach Arena.mp4
```

## Why OneDrive (and not Google Photos)

- **Samsung Gallery has OneDrive sync built in** — no app to install.
  Phone: *Gallery → Settings → Sync with OneDrive* (sign in once).
- The Google Photos API was locked down in March 2025 — no third-party
  automation can read your camera photos from it anymore, and it stripped
  GPS data even before that. OneDrive keeps full EXIF, and its API even
  exposes **date taken** and **GPS coordinates** directly on each photo,
  so most photos are sorted without ever downloading them.
- Everything stays inside one Microsoft account: photos are organized by
  fast **server-side copies**, and only **one** account connection is
  needed.

Phone setup checklist (one time):
1. Samsung Gallery → Settings → **Sync with OneDrive** → sign in.
2. Wait for a few photos to appear in OneDrive under
   `Pictures/Samsung Gallery/DCIM/Camera` (path can vary slightly — the
   script auto-detects common variants, see `source_folder_candidates`).
3. That's it. Screenshots live in a *different* synced album folder, and
   the script only reads the `Camera` folder — so screenshots are never
   touched unless you move them there yourself. (A filename filter for
   `screenshot` is a second line of defense.)

## What each run does (the exact workflow steps)

| # | Step | Composio tool |
|---|------|---------------|
| 1 | Find (or create once) the `Travel Photos` root + subfolders | `ONE_DRIVE_ONEDRIVE_FIND_FOLDER`, `ONE_DRIVE_ONEDRIVE_CREATE_FOLDER` |
| 2 | List photos in the camera folder with metadata (`photo.takenDateTime`, `location`, content hashes) | `ONE_DRIVE_LIST_FOLDER_CHILDREN` |
| 3 | Skip already-processed files (by item ID) and duplicates (by SHA-1/QuickXor content hash) | local state + `_Logs/photo-log.csv` |
| 4 | Read date taken + GPS from OneDrive's metadata; if missing, download the file and parse EXIF locally (Pillow) | `ONE_DRIVE_DOWNLOAD_FILE` (fallback only) |
| 5 | Reverse-geocode GPS → exact city, state, country **and landmark/POI** via OpenStreetMap Nominatim (free, no account; only coordinates are sent — never photos or names). Offline fallback (`reverse-geocode` package) if unreachable or disabled | — |
| 6 | Ensure `Travel Photos/<Year>/<Country>` (or `<Year>/<State>` for domestic) exists | `ONE_DRIVE_ONEDRIVE_CREATE_FOLDER` |
| 7 | **Server-side copy** into the country/state folder; the copy is named with its city + landmark (`IMG — Villa de Juárez — Viña de Liceaga.jpg`); originals untouched | `ONE_DRIVE_COPY_ITEM` |
| 8 | No GPS → `Needs Review/No Location`; ambiguous GPS (nearest known town > 50 km away) → `Needs Review/Unclear Location` | same as 6–7 |
| 9 | Append a row per photo to `_Logs/photo-log.csv` (file name, date taken, city, country, folder path, upload status, duplicate status) | `ONE_DRIVE_ONEDRIVE_CREATE_TEXT_FILE` (replace mode) |

## Required connected apps

| App | Needed? | Why |
|-----|---------|-----|
| **OneDrive** | ✅ the only required connection | read camera folder, create folders, copy files, write the CSV log |
| Google Photos / Google Drive | ❌ | not used at all |
| Maps / geocoding APIs | ❌ | geocoding is done offline — better privacy, no extra account |

## Safest permission settings

Microsoft's OAuth doesn't offer "one folder only" access for personal
OneDrive, so the layers of protection are:

1. **Code-level sandbox (always on):** the camera folder is read-only to
   this script; every write starts from the `Travel Photos` folder ID. It
   never calls delete, rename, move, trash, or share endpoints at all —
   photos are only ever *copied*, and nothing is ever made public.
   `conflict_behavior` is set so nothing is ever overwritten either.
2. **Consent screen:** when you connect OneDrive through Composio you'll
   see Microsoft's consent screen listing the exact permissions
   (Files.ReadWrite — read/write your OneDrive files). Nothing connects
   without your click, and you can revoke access anytime at
   https://account.live.com/consent/Manage.
3. **Maximum isolation (optional):** use a separate Microsoft account
   whose OneDrive contains only synced photos, and point Samsung Gallery
   sync at it.

## Setup

```bash
cd travel-photo-organizer
pip install -r requirements.txt
cp config.example.json config.json     # then edit to taste
export COMPOSIO_API_KEY=...            # from https://platform.composio.dev
```

Connect OneDrive once (Microsoft consent screen — nothing connects
without your click): either from the Composio dashboard, or via the
Composio SDK/MCP `COMPOSIO_MANAGE_CONNECTIONS` for toolkit `one_drive`.

## Test run first (5 photos)

Test mode is **on by default** (`"test_mode": true` in config):

```bash
python organize_photos.py --dry-run   # step 0: prints the plan, writes NOTHING
python organize_photos.py --test      # step 1: processes exactly 5 photos
# check the folders + _Logs/photo-log.csv in OneDrive, then:
python organize_photos.py --limit 50  # step 2: a bigger batch
python organize_photos.py --full      # step 3: whole camera folder
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
| `root_folder_name` | `Travel Photos` | the only OneDrive folder ever written to |
| `source_folder_candidates` | Samsung Gallery / Camera Roll paths | where to look for synced camera photos (first match wins; read-only) |
| `test_mode` / `max_photos_per_run` | `true` / `5` | safety limit until you disable it |
| `include_videos` | `true` | organize videos too (phone videos carry GPS just like photos) |
| `skip_name_patterns` | `["screenshot", "-WA0"]` | never organize matching files (screenshots, WhatsApp media) |
| `unclear_location_km_threshold` | `50` | GPS farther than this from any known town → Unclear Location |
| `big_city_population` | `250000` | offline fallback only: places smaller than this roll up to their municipality (Accra not Osu) |
| `use_online_geocoding` | `true` | exact city + landmark via OpenStreetMap; `false` = fully offline, city-level only |
| `append_place_to_copy_name` | `true` | copies get city + landmark in their name (originals never renamed) |
| `home_country` | `United States` | photos in this country are foldered by state instead of country |

## Guarantees

- Originals in the camera folder are **never deleted, renamed, edited, or moved**.
- Nothing is **ever shared** — no sharing API is called anywhere.
- Nothing is **ever overwritten** — copies fail safely if a name collides.
- Geocoding sends **only GPS coordinates** to OpenStreetMap's nonprofit Nominatim service — never photos, names, or anything else. Set `use_online_geocoding: false` for fully-offline geocoding (city-level only, no landmarks).
- Duplicates (identical content, by hash) are detected and skipped.
- Every photo's outcome is recorded in `Travel Photos/_Logs/photo-log.csv`.
