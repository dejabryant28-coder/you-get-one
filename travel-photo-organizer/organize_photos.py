#!/usr/bin/env python3
"""Travel Photo Organizer — sorts phone photos in Google Drive by location.

Pipeline (runs entirely inside a single "Travel Photos" Drive folder):

  Travel Photos/_Inbox  (phone auto-uploads land here)
        │ read EXIF date + GPS (from Drive's imageMediaMetadata, or the
        │ file bytes as a fallback), reverse-geocode OFFLINE
        ▼
  Travel Photos/<Year>/<Country>/<City>/<Month Year or Trip Name>/photo.jpg
        │ (copied, never moved — originals in _Inbox are untouched)
        ▼
  Travel Photos/_Logs/photo-log.csv  (one row per photo)

Photos with no GPS      -> Travel Photos/Needs Review/No Location
Photos with unclear GPS -> Travel Photos/Needs Review/Unclear Location
Duplicates (same MD5)   -> skipped, logged as duplicate
Screenshots / filtered  -> skipped entirely (never uploaded anywhere)

Safety guarantees enforced by this code:
  * Only ever writes inside the "Travel Photos" folder tree.
  * Never deletes, renames, edits, moves, or shares any photo.
  * Reverse geocoding is offline (reverse_geocoder package) — GPS
    coordinates are never sent to any third-party geocoding service.

Usage:
  python organize_photos.py            # respects config.json (test mode = 5 photos)
  python organize_photos.py --test     # force test mode (5 photos)
  python organize_photos.py --limit 20 # process at most 20 photos
  python organize_photos.py --full     # no limit (only after test runs look good)
  python organize_photos.py --dry-run  # print what WOULD happen; no writes at all

Requires env var COMPOSIO_API_KEY (and optionally COMPOSIO_USER_ID).
"""

import argparse
import csv
import io
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    from composio import Composio
except ImportError:
    sys.exit("Missing dependency. Run: pip install -r requirements.txt")

HERE = Path(__file__).resolve().parent
STATE_PATH = HERE / "state" / "processed.json"
FOLDER_MIME = "application/vnd.google-apps.folder"

LOG_COLUMNS = [
    "file_name", "date_taken", "detected_city", "detected_country",
    "drive_folder_path", "upload_status", "duplicate_status",
    "md5", "source_file_id", "processed_at_utc",
]


# ---------------------------------------------------------------- config ---

def load_config():
    path = HERE / "config.json"
    if not path.exists():
        path = HERE / "config.example.json"
        print(f"NOTE: no config.json found, using defaults from {path.name}")
    with open(path) as f:
        return json.load(f)


# ------------------------------------------------------- composio client ---

class Drive:
    """Thin wrapper over Composio's Google Drive tools."""

    def __init__(self, dry_run=False):
        api_key = os.environ.get("COMPOSIO_API_KEY")
        if not api_key:
            sys.exit("Set COMPOSIO_API_KEY in your environment first.")
        self.client = Composio(api_key=api_key)
        self.user_id = os.environ.get("COMPOSIO_USER_ID", "default")
        self.dry_run = dry_run

    def call(self, slug, arguments):
        res = self.client.tools.execute(slug, user_id=self.user_id,
                                        arguments=arguments)
        if isinstance(res, dict):
            ok, data, err = res.get("successful"), res.get("data"), res.get("error")
        else:  # SDK object form
            ok, data, err = res.successful, res.data, res.error
        if not ok:
            raise RuntimeError(f"{slug} failed: {err}")
        return data or {}

    # -- read-only operations (always allowed, even in dry runs) ----------

    def find_child_folder(self, parent_id, name):
        safe = name.replace("'", "\\'")
        data = self.call("GOOGLEDRIVE_FIND_FILE", {
            "q": (f"name = '{safe}' and mimeType = '{FOLDER_MIME}' "
                  f"and '{parent_id}' in parents and trashed = false"),
            "corpora": "user",
            "pageSize": 5,
        })
        files = data.get("files") or []
        return files[0]["id"] if files else None

    def find_root_folder(self, name):
        return self.find_child_folder("root", name)

    def list_photos(self, folder_id, include_videos):
        mime_q = "mimeType contains 'image/'"
        if include_videos:
            mime_q = "(mimeType contains 'image/' or mimeType contains 'video/')"
        files, page_token = [], None
        while True:
            args = {
                "folder_id": folder_id,
                "q": f"{mime_q} and trashed = false",
                "corpora": "user",
                "orderBy": "createdTime",
                "pageSize": 200,
                "fields": ("nextPageToken,files(id,name,mimeType,md5Checksum,"
                           "createdTime,size,imageMediaMetadata)"),
            }
            if page_token:
                args["pageToken"] = page_token
            data = self.call("GOOGLEDRIVE_FIND_FILE", args)
            files.extend(data.get("files") or [])
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return files

    def find_file_in_folder(self, parent_id, name):
        safe = name.replace("'", "\\'")
        data = self.call("GOOGLEDRIVE_FIND_FILE", {
            "q": f"name = '{safe}' and '{parent_id}' in parents and trashed = false",
            "corpora": "user",
            "pageSize": 5,
        })
        files = data.get("files") or []
        return files[0]["id"] if files else None

    def download_bytes(self, file_id):
        """Download a file's raw bytes (used only for EXIF fallback + log)."""
        data = self.call("GOOGLEDRIVE_DOWNLOAD_FILE", {"fileId": file_id})
        ref = _find_file_ref(data)
        if ref is None:
            raise RuntimeError(f"no downloadable content for {file_id}")
        if re.match(r"^https?://", ref):
            r = requests.get(ref, timeout=120)
            r.raise_for_status()
            return r.content
        return Path(ref).read_bytes()

    # -- write operations (blocked in dry runs) ----------------------------

    def create_folder(self, parent_id, name):
        if self.dry_run:
            print(f"  [dry-run] would create folder '{name}'")
            return f"dryrun-folder-{name}"
        data = self.call("GOOGLEDRIVE_CREATE_FOLDER",
                         {"name": name, "parent_id": parent_id})
        folder_id = data.get("id") or (data.get("file") or {}).get("id")
        if not folder_id:
            raise RuntimeError(f"CREATE_FOLDER returned no id: {data}")
        return folder_id

    def copy_file(self, file_id, dest_folder_id, name):
        if self.dry_run:
            print(f"  [dry-run] would copy '{name}' -> folder {dest_folder_id}")
            return "dryrun-copy"
        data = self.call("GOOGLEDRIVE_COPY_FILE_ADVANCED", {
            "fileId": file_id,
            "parents": [dest_folder_id],
            "name": name,  # keep original name, avoid "Copy of ..."
        })
        return data.get("id") or (data.get("file") or {}).get("id")

    def create_text_file(self, parent_id, name, content, mime="text/csv"):
        if self.dry_run:
            print(f"  [dry-run] would create '{name}' in {parent_id}")
            return "dryrun-textfile"
        data = self.call("GOOGLEDRIVE_CREATE_FILE_FROM_TEXT", {
            "file_name": name, "text_content": content,
            "parent_id": parent_id, "mime_type": mime,
        })
        return data.get("id")

    def update_text_file(self, file_id, content, mime="text/csv"):
        if self.dry_run:
            print(f"  [dry-run] would update log file {file_id}")
            return
        self.call("GOOGLEDRIVE_EDIT_FILE", {
            "file_id": file_id, "content": content, "mime_type": mime,
        })


def _find_file_ref(obj):
    """Recursively find a URL or local path in a Composio download response."""
    if isinstance(obj, str):
        if re.match(r"^https?://", obj) or os.path.exists(obj):
            return obj
        return None
    if isinstance(obj, dict):
        for key in ("s3url", "s3key", "uri", "url", "file_path", "path"):
            if key in obj:
                ref = _find_file_ref(obj[key])
                if ref:
                    return ref
        for v in obj.values():
            ref = _find_file_ref(v)
            if ref:
                return ref
    if isinstance(obj, list):
        for v in obj:
            ref = _find_file_ref(v)
            if ref:
                return ref
    return None


# ----------------------------------------------------------- exif / dates ---

def parse_photo_datetime(value):
    """Accept EXIF ('2026:07:04 18:23:11') and RFC3339 timestamps."""
    if not value:
        return None
    value = str(value).strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def exif_from_bytes(raw):
    """Fallback EXIF parse when Drive didn't surface metadata. Returns
    (datetime_or_None, (lat, lng)_or_None)."""
    from PIL import Image
    from PIL.ExifTags import GPSTAGS, TAGS

    def dms_to_deg(dms, ref):
        deg = float(dms[0]) + float(dms[1]) / 60 + float(dms[2]) / 3600
        return -deg if ref in ("S", "W") else deg

    try:
        img = Image.open(io.BytesIO(raw))
        exif = img._getexif() or {}
    except Exception:
        return None, None

    named = {TAGS.get(k, k): v for k, v in exif.items()}
    taken = parse_photo_datetime(named.get("DateTimeOriginal") or named.get("DateTime"))

    gps = None
    if "GPSInfo" in named:
        g = {GPSTAGS.get(k, k): v for k, v in named["GPSInfo"].items()}
        try:
            lat = dms_to_deg(g["GPSLatitude"], g.get("GPSLatitudeRef", "N"))
            lng = dms_to_deg(g["GPSLongitude"], g.get("GPSLongitudeRef", "E"))
            if (lat, lng) != (0.0, 0.0):
                gps = (lat, lng)
        except (KeyError, TypeError, ZeroDivisionError):
            gps = None
    return taken, gps


# ------------------------------------------------------ offline geocoding ---

def haversine_km(a, b):
    lat1, lng1, lat2, lng2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(h))


def reverse_geocode(lat, lng, unclear_km):
    """Offline reverse geocode. Returns (city, country, clear: bool)."""
    import pycountry
    import reverse_geocoder

    hit = reverse_geocoder.search([(lat, lng)], mode=1)[0]
    city = hit.get("name") or ""
    cc = hit.get("cc") or ""
    country = cc
    if cc:
        rec = pycountry.countries.get(alpha_2=cc)
        if rec:
            country = getattr(rec, "common_name", None) or rec.name
    try:
        dist = haversine_km((lat, lng), (float(hit["lat"]), float(hit["lon"])))
    except (KeyError, ValueError):
        dist = float("inf")
    clear = bool(city and country) and dist <= unclear_km
    return city, country, clear


# ----------------------------------------------------------------- state ---

def load_state():
    if STATE_PATH.exists():
        with open(STATE_PATH) as f:
            return json.load(f)
    return {"processed_md5": [], "processed_ids": [], "folder_ids": {},
            "log_file_id": None}


def save_state(state, dry_run):
    if dry_run:
        return
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def rebuild_state_from_log(drive, state, log_file_id):
    """Fresh machine: rebuild the dedup sets from the CSV log in Drive."""
    try:
        raw = drive.download_bytes(log_file_id).decode("utf-8", "replace")
    except Exception as e:
        print(f"  (could not rebuild state from Drive log: {e})")
        return
    reader = csv.DictReader(io.StringIO(raw))
    for row in reader:
        if row.get("md5"):
            state["processed_md5"].append(row["md5"])
        if row.get("source_file_id"):
            state["processed_ids"].append(row["source_file_id"])
    print(f"  rebuilt dedup state from Drive log: "
          f"{len(state['processed_ids'])} photos already processed")


# ------------------------------------------------------------ folder tree ---

class FolderTree:
    """Creates/caches folders strictly under the Travel Photos root."""

    def __init__(self, drive, root_id, state):
        self.drive = drive
        self.root_id = root_id
        self.cache = state["folder_ids"]

    def ensure_path(self, *names):
        parent, key_parts = self.root_id, []
        for name in names:
            key_parts.append(name)
            key = "/".join(key_parts)
            folder_id = self.cache.get(key)
            if not folder_id:
                folder_id = (self.drive.find_child_folder(parent, name)
                             or self.drive.create_folder(parent, name))
                self.cache[key] = folder_id
            parent = folder_id
        return parent


# ------------------------------------------------------------------- log ---

def append_log_rows(drive, tree, state, cfg, new_rows):
    if not new_rows:
        return
    logs_id = tree.ensure_path(cfg["logs_folder_name"])
    log_name = cfg["log_file_name"]

    log_file_id = state.get("log_file_id")
    if not log_file_id and not drive.dry_run:
        log_file_id = drive.find_file_in_folder(logs_id, log_name)

    if log_file_id and not drive.dry_run:
        existing = drive.download_bytes(log_file_id).decode("utf-8", "replace")
        if not existing.endswith("\n"):
            existing += "\n"
    else:
        existing = ",".join(LOG_COLUMNS) + "\n"

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=LOG_COLUMNS)
    for row in new_rows:
        writer.writerow(row)
    content = existing + buf.getvalue()

    if log_file_id:
        drive.update_text_file(log_file_id, content)
    else:
        log_file_id = drive.create_text_file(logs_id, log_name, content)
    state["log_file_id"] = log_file_id


# ------------------------------------------------------------------ main ---

def leaf_folder_name(taken, trips):
    """'July 2026' by default, or a configured trip name if the date matches."""
    for trip in trips or []:
        try:
            start = datetime.strptime(trip["start"], "%Y-%m-%d")
            end = datetime.strptime(trip["end"], "%Y-%m-%d")
        except (KeyError, ValueError):
            continue
        if start.date() <= taken.date() <= end.date():
            return trip["name"]
    return taken.strftime("%B %Y")


def should_skip_name(name, patterns):
    low = name.lower()
    return any(p.lower() in low for p in patterns)


def process(cfg, limit, dry_run):
    drive = Drive(dry_run=dry_run)
    state = load_state()
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Resolve the sandbox root. Refuse to invent it silently in a weird
    #    place: create it at My Drive root only if it does not exist yet.
    root_name = cfg["root_folder_name"]
    root_id = drive.find_root_folder(root_name)
    if not root_id:
        print(f"Creating '{root_name}' in My Drive root...")
        if dry_run:
            print("  [dry-run] stopping here — root folder does not exist yet.")
            return
        root_id = drive.create_folder("root", root_name)
    tree = FolderTree(drive, root_id, state)

    inbox_id = tree.ensure_path(cfg["inbox_folder_name"])

    # 2. Rebuild dedup state from the Drive log if this machine has none.
    if not state["processed_ids"] and not state["processed_md5"]:
        logs_id = tree.ensure_path(cfg["logs_folder_name"])
        existing_log = None if dry_run else drive.find_file_in_folder(
            logs_id, cfg["log_file_name"])
        if existing_log:
            state["log_file_id"] = existing_log
            rebuild_state_from_log(drive, state, existing_log)

    processed_md5 = set(state["processed_md5"])
    processed_ids = set(state["processed_ids"])

    # 3. List inbox photos.
    photos = drive.list_photos(inbox_id, cfg.get("include_videos", False))
    pending = [p for p in photos if p["id"] not in processed_ids]
    print(f"Inbox: {len(photos)} media files, {len(pending)} not yet processed.")
    if limit:
        pending = pending[:limit]
        print(f"Processing at most {limit} this run"
              f"{' (TEST MODE)' if limit <= cfg.get('max_photos_per_run', 5) else ''}.")

    new_rows = []
    for photo in pending:
        name, file_id = photo["name"], photo["id"]
        md5 = photo.get("md5Checksum") or ""
        print(f"\n• {name}")
        row = dict.fromkeys(LOG_COLUMNS, "")
        row.update(file_name=name, source_file_id=file_id, md5=md5,
                   processed_at_utc=now_iso, duplicate_status="unique")

        # Screenshots / filtered files: never uploaded anywhere.
        if should_skip_name(name, cfg.get("skip_name_patterns", [])):
            print("  skipped (matches skip_name_patterns — not organized)")
            row.update(upload_status="skipped (name filter)")
            new_rows.append(row)
            processed_ids.add(file_id)
            continue

        # Duplicate by content hash.
        if md5 and md5 in processed_md5:
            print("  duplicate (same MD5 already organized) — skipping copy")
            row.update(upload_status="skipped", duplicate_status="duplicate")
            new_rows.append(row)
            processed_ids.add(file_id)
            continue

        # Date taken + GPS: prefer Drive's parsed EXIF, fall back to bytes.
        meta = photo.get("imageMediaMetadata") or {}
        taken = parse_photo_datetime(meta.get("time"))
        loc = meta.get("location") or {}
        gps = None
        if loc.get("latitude") is not None and loc.get("longitude") is not None:
            if (loc["latitude"], loc["longitude"]) != (0, 0):
                gps = (loc["latitude"], loc["longitude"])

        if taken is None or gps is None:
            try:
                raw = drive.download_bytes(file_id)
                exif_taken, exif_gps = exif_from_bytes(raw)
                taken = taken or exif_taken
                gps = gps or exif_gps
            except Exception as e:
                print(f"  (EXIF fallback failed: {e})")
        taken = taken or parse_photo_datetime(photo.get("createdTime")) \
            or datetime.now()
        row["date_taken"] = taken.strftime("%Y-%m-%d %H:%M:%S")

        # Route to destination folder.
        if gps is None:
            dest_parts = ["Needs Review", "No Location"]
            print("  no GPS data -> Needs Review / No Location")
        else:
            city, country, clear = reverse_geocode(
                gps[0], gps[1], cfg.get("unclear_location_km_threshold", 50))
            row.update(detected_city=city, detected_country=country)
            if clear:
                dest_parts = [str(taken.year), country, city,
                              leaf_folder_name(taken, cfg.get("trips"))]
                print(f"  {gps[0]:.4f},{gps[1]:.4f} -> {country} / {city}")
            else:
                dest_parts = ["Needs Review", "Unclear Location"]
                print("  GPS present but ambiguous -> Needs Review / Unclear Location")

        dest_id = tree.ensure_path(*dest_parts)
        path_str = "/".join([cfg["root_folder_name"]] + dest_parts)
        row["drive_folder_path"] = path_str

        try:
            drive.copy_file(file_id, dest_id, name)
            row["upload_status"] = "uploaded" if not dry_run else "dry-run"
            print(f"  copied -> {path_str}")
        except Exception as e:
            row["upload_status"] = f"error: {e}"
            print(f"  COPY FAILED: {e}")
            new_rows.append(row)
            continue  # do not mark processed; retried next run

        processed_ids.add(file_id)
        if md5:
            processed_md5.add(md5)
        new_rows.append(row)

    # 4. Persist log + state.
    state["processed_md5"] = sorted(processed_md5)
    state["processed_ids"] = sorted(processed_ids)
    append_log_rows(drive, tree, state, cfg, new_rows)
    save_state(state, dry_run)

    done = sum(1 for r in new_rows if r["upload_status"] in ("uploaded", "dry-run"))
    dups = sum(1 for r in new_rows if r["duplicate_status"] == "duplicate")
    print(f"\nDone. {done} organized, {dups} duplicates skipped, "
          f"{len(new_rows) - done - dups} other/skipped. "
          f"Log: {cfg['root_folder_name']}/{cfg['logs_folder_name']}/{cfg['log_file_name']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test", action="store_true", help="process only 5 photos")
    ap.add_argument("--limit", type=int, help="process at most N photos")
    ap.add_argument("--full", action="store_true", help="no photo limit")
    ap.add_argument("--dry-run", action="store_true",
                    help="print planned actions; write nothing to Drive")
    args = ap.parse_args()

    cfg = load_config()
    if args.full:
        limit = args.limit or None
    elif args.limit:
        limit = args.limit
    elif args.test or cfg.get("test_mode", True):
        limit = cfg.get("max_photos_per_run", 5)
    else:
        limit = None

    process(cfg, limit, args.dry_run or cfg.get("dry_run", False))


if __name__ == "__main__":
    main()
