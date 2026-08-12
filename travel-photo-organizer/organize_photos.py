#!/usr/bin/env python3
"""Travel Photo Organizer — sorts Samsung phone photos in OneDrive by location.

Pipeline (everything happens inside your OneDrive):

  /Pictures/Samsung Gallery/DCIM/Camera   (Samsung Gallery's built-in
        │                                  OneDrive sync puts photos here)
        │ read date taken + GPS (OneDrive exposes both on each photo;
        │ EXIF parsed from the file bytes as a fallback),
        │ reverse-geocode OFFLINE
        ▼
  /Travel Photos/<Year>/<Country>/<City>/<Month Year or Trip Name>/photo.jpg
        │ (server-side COPY — originals in the camera folder are untouched)
        ▼
  /Travel Photos/_Logs/photo-log.csv      (one row per photo)

Photos with no GPS      -> Travel Photos/Needs Review/No Location
Photos with unclear GPS -> Travel Photos/Needs Review/Unclear Location
Duplicates (same hash)  -> skipped, logged as duplicate
Screenshots / filtered  -> skipped entirely (never copied anywhere)

Safety guarantees enforced by this code:
  * The source camera folder is READ-ONLY to this script.
  * Only ever writes inside the "Travel Photos" folder tree.
  * Never deletes, renames, edits, moves, or shares anything.
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
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    from composio import Composio
except ImportError:
    sys.exit("Missing dependency. Run: pip install -r requirements.txt")

HERE = Path(__file__).resolve().parent
STATE_PATH = HERE / "state" / "processed.json"

LOG_COLUMNS = [
    "file_name", "date_taken", "detected_city", "detected_country",
    "landmark", "address", "folder_path", "upload_status",
    "duplicate_status", "content_hash", "source_item_id", "processed_at_utc",
]

CHILD_FIELDS = ["id", "name", "size", "file", "folder", "photo", "location",
                "createdDateTime", "lastModifiedDateTime"]


# ---------------------------------------------------------------- config ---

def load_config():
    path = HERE / "config.json"
    if not path.exists():
        path = HERE / "config.example.json"
        print(f"NOTE: no config.json found, using defaults from {path.name}")
    with open(path) as f:
        return json.load(f)


# ------------------------------------------------------- composio client ---

class OneDrive:
    """Thin wrapper over Composio's OneDrive tools."""

    def __init__(self, dry_run=False):
        api_key = os.environ.get("COMPOSIO_API_KEY")
        if not api_key:
            sys.exit("Set COMPOSIO_API_KEY in your environment first.")
        self.client = Composio(api_key=api_key)
        self.user_id = os.environ.get("COMPOSIO_USER_ID", "default")
        self.dry_run = dry_run
        self._drive_id = None

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

    @property
    def drive_id(self):
        if not self._drive_id:
            data = self.call("ONE_DRIVE_LIST_DRIVES", {"top": 5})
            drives = _first_list(data, "value") or []
            if not drives:
                raise RuntimeError("no OneDrive drives visible for this account")
            self._drive_id = drives[0]["id"]
        return self._drive_id

    def list_children(self, folder_ref, select=None):
        """List direct children of a folder by path ('/Pictures/...') or ID."""
        items, page_token = [], None
        while True:
            args = {"use_me_drive": True, "top": 200,
                    "select": select or CHILD_FIELDS}
            if folder_ref.startswith("/"):
                args["folder_path"] = folder_ref
            else:
                args["folder_item_id"] = folder_ref
            if page_token:
                args["page_token"] = page_token
            data = self.call("ONE_DRIVE_LIST_FOLDER_CHILDREN", args)
            items.extend(_first_list(data, "value") or [])
            page_token = (data.get("next_page_token")
                          or data.get("nextPageToken"))
            if not page_token:
                break
        return items

    def find_child_folder(self, parent_ref, name):
        data = self.call("ONE_DRIVE_ONEDRIVE_FIND_FOLDER",
                         {"folder": parent_ref, "name": name})
        hits = _first_list(data, "value") or _first_list(data, "folders") or []
        for hit in hits:
            if hit.get("name") == name:
                return hit["id"]
        return None

    def find_child_file(self, parent_ref, name):
        for item in self.list_children(parent_ref, select=["id", "name", "file"]):
            if item.get("name") == name and "file" in item:
                return item["id"]
        return None

    def download_bytes(self, item_id, file_name):
        data = self.call("ONE_DRIVE_DOWNLOAD_FILE",
                         {"item_id": item_id, "file_name": file_name})
        ref = _find_file_ref(data)
        if ref is None:
            raise RuntimeError(f"no downloadable content for {item_id}")
        if re.match(r"^https?://", ref):
            r = requests.get(ref, timeout=180, allow_redirects=True)
            r.raise_for_status()
            return r.content
        return Path(ref).read_bytes()

    # -- write operations (blocked in dry runs) ----------------------------

    def create_folder(self, parent_ref, name):
        if self.dry_run:
            print(f"  [dry-run] would create folder '{name}'")
            return f"dryrun-folder-{name}"
        try:
            data = self.call("ONE_DRIVE_ONEDRIVE_CREATE_FOLDER", {
                "name": name, "parent_folder": parent_ref,
                "conflict_behavior": "fail",  # never auto-rename to 'Ghana 1'
            })
            folder_id = _find_id(data)
            if folder_id:
                return folder_id
        except RuntimeError:
            pass  # probably created moments ago / already exists
        existing = self.find_child_folder(parent_ref, name)
        if existing:
            return existing
        raise RuntimeError(f"could not create or find folder '{name}'")

    def copy_file(self, item_id, dest_folder_id, name):
        """Server-side copy. Returns status string; original is untouched."""
        if self.dry_run:
            print(f"  [dry-run] would copy '{name}' -> folder {dest_folder_id}")
            return "dry-run"
        try:
            self.call("ONE_DRIVE_COPY_ITEM", {
                "item_id": item_id,
                "parent_reference": {"driveId": self.drive_id,
                                     "id": dest_folder_id},
                "name": name,
                "conflict_behavior": "fail",
            })
        except RuntimeError as e:
            if "nameAlreadyExists" in str(e) or "409" in str(e):
                return "already-existed"
            raise
        # Copy is asynchronous; verify it landed (brief retries).
        for _ in range(5):
            time.sleep(2)
            if self.find_child_file(dest_folder_id, name):
                return "uploaded"
        return "copy-started (verify later)"

    def write_text_file(self, folder_id, name, content):
        if self.dry_run:
            print(f"  [dry-run] would write '{name}' ({len(content)} bytes)")
            return
        self.call("ONE_DRIVE_ONEDRIVE_CREATE_TEXT_FILE", {
            "name": name, "folder": folder_id, "content": content,
            "conflict_behavior": "replace",
        })


def _first_list(obj, key):
    """Find the first list under `key` anywhere in a nested response."""
    if isinstance(obj, dict):
        if isinstance(obj.get(key), list):
            return obj[key]
        for v in obj.values():
            found = _first_list(v, key)
            if found is not None:
                return found
    return None


def _find_id(obj):
    if isinstance(obj, dict):
        if isinstance(obj.get("id"), str):
            return obj["id"]
        for v in obj.values():
            found = _find_id(v)
            if found:
                return found
    return None


def _find_file_ref(obj):
    """Recursively find a URL or local path in a Composio download response."""
    if isinstance(obj, str):
        if re.match(r"^https?://", obj) or os.path.exists(obj):
            return obj
        return None
    if isinstance(obj, dict):
        for key in ("s3url", "s3key", "uri", "url", "downloadUrl",
                    "@microsoft.graph.downloadUrl", "file_path", "path"):
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
    """Accept EXIF ('2026:07:04 18:23:11') and ISO/RFC3339 timestamps."""
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
    """Fallback EXIF parse when OneDrive didn't surface metadata. Returns
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


NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
POI_CATEGORIES = {"amenity", "tourism", "leisure", "shop", "craft", "historic",
                  "building", "man_made", "natural", "aeroway", "office"}
_geo_cache, _last_geo_call = {}, [0.0]


def sanitize_name(name, max_len=60):
    """Make a string safe as a OneDrive folder/file-name fragment."""
    name = re.sub(r"\s*\([^)]*\)", "", name)          # drop parentheticals
    name = re.sub(r'[<>:"/\\|?*]', "-", name).strip(" .")
    return name[:max_len].strip()


def reverse_geocode_online(lat, lng):
    """OpenStreetMap Nominatim lookup (free, no account). Sends ONLY the
    coordinates — never photos or file names. Returns
    (city, country, landmark, address) or None on failure.
    Rate-limited to 1 request/second per Nominatim's usage policy;
    results are cached per ~11 m grid cell."""
    key = (round(lat, 4), round(lng, 4))
    if key in _geo_cache:
        return _geo_cache[key]
    wait = 1.1 - (time.time() - _last_geo_call[0])
    if wait > 0:
        time.sleep(wait)
    try:
        r = requests.get(NOMINATIM_URL, params={
            "lat": lat, "lon": lng, "format": "jsonv2",
            "zoom": 18, "accept-language": "en",
        }, headers={"User-Agent": "travel-photo-organizer/1.0 (personal use)"},
            timeout=30)
        _last_geo_call[0] = time.time()
        r.raise_for_status()
        d = r.json()
    except Exception:
        _last_geo_call[0] = time.time()
        return None

    addr = d.get("address") or {}
    city = (addr.get("city") or addr.get("town") or addr.get("village")
            or addr.get("municipality") or addr.get("county") or "")
    city = sanitize_name(re.sub(r"^(Municipio de|Municipality of)\s+", "", city))
    for suffix in (" County", " Municipality", " District"):
        city = city.removesuffix(suffix)
    state = sanitize_name(addr.get("state") or addr.get("region") or "")
    country = addr.get("country") or ""
    landmark = ""
    if d.get("category") in POI_CATEGORIES and d.get("name"):
        landmark = sanitize_name(d["name"])
    result = (city, state, country, landmark, d.get("display_name", ""))
    _geo_cache[key] = result
    return result


def reverse_geocode(lat, lng, unclear_km, big_city_population=250000):
    """Offline reverse geocode (fallback when Nominatim is off/unreachable).
    Returns (city, state, country, clear: bool).

    The GeoNames data behind reverse-geocode often matches neighborhoods
    or villages (Osu, Intendente, Rancho Verde), so unless the matched
    place is itself a big city, roll up to its municipality/state —
    giving Accra, Lisbon, Ensenada instead."""
    import reverse_geocode as rg

    hit = rg.search([(lat, lng)])[0]
    city = hit.get("city") or ""
    if (hit.get("population") or 0) < big_city_population:
        city = hit.get("county") or hit.get("state") or city
        for suffix in (" County", " Municipality", " District"):
            city = city.removesuffix(suffix)
    state = hit.get("state") or ""
    country = hit.get("country") or hit.get("country_code") or ""
    if "latitude" in hit and "longitude" in hit:
        dist = haversine_km((lat, lng), (hit["latitude"], hit["longitude"]))
    else:
        dist = float("inf")
    clear = bool(city and country) and dist <= unclear_km
    return city, state, country, clear


# ----------------------------------------------------------------- state ---

def load_state():
    if STATE_PATH.exists():
        with open(STATE_PATH) as f:
            return json.load(f)
    return {"processed_hashes": [], "processed_ids": [], "folder_ids": {},
            "source_folder": None}


def save_state(state, dry_run):
    if dry_run:
        return
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def rebuild_state_from_log(existing_csv, state):
    reader = csv.DictReader(io.StringIO(existing_csv))
    for row in reader:
        if row.get("content_hash"):
            state["processed_hashes"].append(row["content_hash"])
        if row.get("source_item_id"):
            state["processed_ids"].append(row["source_item_id"])
    print(f"  rebuilt dedup state from OneDrive log: "
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

def photo_hash(item):
    hashes = (item.get("file") or {}).get("hashes") or {}
    return (hashes.get("sha1Hash") or hashes.get("quickXorHash")
            or hashes.get("sha256Hash") or "")


def is_image(item, include_videos):
    mime = ((item.get("file") or {}).get("mimeType") or "").lower()
    if mime.startswith("image/"):
        return True
    return include_videos and mime.startswith("video/")


def should_skip_name(name, patterns):
    low = name.lower()
    return any(p.lower() in low for p in patterns)


# ------------------------------------------------------------------ main ---

def resolve_source_folder(drive, cfg, state):
    """Find the folder where the phone's OneDrive sync drops camera photos."""
    if state.get("source_folder"):
        return state["source_folder"]
    for candidate in cfg["source_folder_candidates"]:
        try:
            drive.list_children(candidate, select=["id", "name"])
            print(f"Source folder: {candidate}")
            state["source_folder"] = candidate
            return candidate
        except RuntimeError:
            continue
    sys.exit("Could not find your camera folder in OneDrive. Checked: "
             + ", ".join(cfg["source_folder_candidates"])
             + "\nEnable Samsung Gallery -> OneDrive sync (or OneDrive app "
               "camera upload), wait for a first photo to sync, then add the "
               "folder path to 'source_folder_candidates' in config.json.")


def process(cfg, limit, dry_run):
    drive = OneDrive(dry_run=dry_run)
    state = load_state()
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    root_name = cfg["root_folder_name"]

    # 1. Resolve the sandbox root (creating it once at OneDrive root).
    root_id = drive.find_child_folder("/", root_name)
    if not root_id:
        print(f"Creating '/{root_name}' in OneDrive root...")
        if dry_run:
            print("  [dry-run] stopping here — root folder does not exist yet.")
            return
        root_id = drive.create_folder("/", root_name)
    tree = FolderTree(drive, root_id, state)

    # 2. Load the existing CSV log (dedup source of truth on fresh machines).
    logs_id = tree.ensure_path(cfg["logs_folder_name"])
    log_name = cfg["log_file_name"]
    existing_csv = None
    if not dry_run:
        log_file_id = drive.find_child_file(logs_id, log_name)
        if log_file_id:
            try:
                existing_csv = drive.download_bytes(
                    log_file_id, log_name).decode("utf-8", "replace")
            except Exception as e:
                print(f"  (could not read existing log: {e})")
    # Older log versions used a different column set (no content_hash /
    # source_item_id). Remap legacy rows into the current schema so the log
    # stays one well-formed CSV and dedup rebuild reads every row.
    if existing_csv:
        header = existing_csv.split("\n", 1)[0].strip()
        if header != ",".join(LOG_COLUMNS):
            legacy = list(csv.DictReader(io.StringIO(existing_csv)))
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=LOG_COLUMNS)
            w.writeheader()
            for old in legacy:
                w.writerow({k: (old.get(k) or "") for k in LOG_COLUMNS})
            existing_csv = buf.getvalue()
            print(f"  normalized legacy log ({len(legacy)} rows) to current columns")
    if existing_csv and not state["processed_ids"] and not state["processed_hashes"]:
        rebuild_state_from_log(existing_csv, state)

    processed_hashes = set(state["processed_hashes"])
    processed_ids = set(state["processed_ids"])

    # 3. List camera photos (source folder is read-only to this script).
    source = resolve_source_folder(drive, cfg, state)
    items = drive.list_children(source)
    photos = [i for i in items if is_image(i, cfg.get("include_videos", False))]
    photos.sort(key=lambda i: i.get("createdDateTime") or "")
    pending = [p for p in photos if p["id"] not in processed_ids]
    print(f"Camera folder: {len(photos)} media files, "
          f"{len(pending)} not yet processed.")
    if limit:
        pending = pending[:limit]
        print(f"Processing at most {limit} this run"
              f"{' (TEST MODE)' if limit <= cfg.get('max_photos_per_run', 5) else ''}.")

    new_rows = []
    for item in pending:
        name, item_id = item["name"], item["id"]
        chash = photo_hash(item)
        print(f"\n• {name}")
        row = dict.fromkeys(LOG_COLUMNS, "")
        row.update(file_name=name, source_item_id=item_id, content_hash=chash,
                   processed_at_utc=now_iso, duplicate_status="unique")

        # Screenshots / filtered files: never copied anywhere.
        if should_skip_name(name, cfg.get("skip_name_patterns", [])):
            print("  skipped (matches skip_name_patterns — not organized)")
            row.update(upload_status="skipped (name filter)")
            new_rows.append(row)
            processed_ids.add(item_id)
            continue

        # Duplicate by content hash.
        if chash and chash in processed_hashes:
            print("  duplicate (same content already organized) — skipping copy")
            row.update(upload_status="skipped", duplicate_status="duplicate")
            new_rows.append(row)
            processed_ids.add(item_id)
            continue

        # Date taken + GPS: prefer OneDrive's photo/location facets.
        photo_meta = item.get("photo") or {}
        taken = parse_photo_datetime(photo_meta.get("takenDateTime"))
        loc = item.get("location") or {}
        gps = None
        if loc.get("latitude") is not None and loc.get("longitude") is not None:
            if (loc["latitude"], loc["longitude"]) != (0, 0):
                gps = (loc["latitude"], loc["longitude"])

        # EXIF download fallback is images-only: the parser is Pillow-based,
        # so pulling a whole video down just to fail the parse wastes
        # bandwidth (camera folders hold saved videos with no metadata).
        mime = (item.get("file") or {}).get("mimeType", "")
        if (taken is None or gps is None) and mime.startswith("image/"):
            try:
                raw = drive.download_bytes(item_id, name)
                exif_taken, exif_gps = exif_from_bytes(raw)
                taken = taken or exif_taken
                gps = gps or exif_gps
            except Exception as e:
                print(f"  (EXIF fallback failed: {e})")
        taken = taken or parse_photo_datetime(item.get("createdDateTime")) \
            or datetime.now()
        row["date_taken"] = taken.strftime("%Y-%m-%d %H:%M:%S")

        # Route to destination folder.
        if gps is None:
            dest_parts = ["Needs Review", "No Location"]
            print("  no GPS data -> Needs Review / No Location")
        else:
            # Exact place via OpenStreetMap (city + landmark), offline fallback.
            hit = (reverse_geocode_online(gps[0], gps[1])
                   if cfg.get("use_online_geocoding", True) else None)
            if hit and hit[0] and hit[2]:
                city, state, country, landmark, address = hit
                clear = True
                row.update(landmark=landmark, address=address)
            else:
                city, state, country, clear = reverse_geocode(
                    gps[0], gps[1], cfg.get("unclear_location_km_threshold", 50),
                    cfg.get("big_city_population", 250000))
            row.update(detected_city=city, detected_country=country)
            # Country allow-list: GPS that resolves to a country you've
            # never visited is almost always corrupted EXIF or media saved
            # from someone else — route it to review, don't invent folders.
            allowed = cfg.get("allowed_countries") or []
            if clear and allowed and country not in allowed:
                clear = False
                print(f"  '{country}' not in allowed_countries -> review")
            if clear:
                # One folder per country; home-country photos group by state.
                place = country
                if country == cfg.get("home_country", "United States") and state:
                    place = state
                dest_parts = [place]
                where = f"{place} / {city}"
                if row["landmark"]:
                    where += f" ({row['landmark']})"
                print(f"  {gps[0]:.4f},{gps[1]:.4f} -> {where}")
            else:
                dest_parts = ["Needs Review", "Unclear Location"]
                print("  GPS present but ambiguous -> Needs Review / Unclear Location")

        dest_id = tree.ensure_path(*dest_parts)
        path_str = "/".join([root_name] + dest_parts)
        row["folder_path"] = path_str

        # Name the COPY with city + landmark (originals are never renamed).
        copy_name = name
        if cfg.get("append_place_to_copy_name", True):
            extra = [x for x in (row["detected_city"], row["landmark"]) if x]
            if extra:
                stem, _, ext = name.rpartition(".")
                suffix = " — " + " — ".join(extra)
                copy_name = f"{stem}{suffix}.{ext}" if ext else name + suffix

        try:
            status = drive.copy_file(item_id, dest_id, copy_name)
            row["upload_status"] = status
            print(f"  {status} -> {path_str}")
        except Exception as e:
            row["upload_status"] = f"error: {e}"
            print(f"  COPY FAILED: {e}")
            new_rows.append(row)
            continue  # do not mark processed; retried next run

        processed_ids.add(item_id)
        if chash:
            processed_hashes.add(chash)
        new_rows.append(row)

    # 4. Persist log + state.
    state["processed_hashes"] = sorted(processed_hashes)
    state["processed_ids"] = sorted(processed_ids)
    if new_rows:
        base = existing_csv if existing_csv else ",".join(LOG_COLUMNS) + "\n"
        if not base.endswith("\n"):
            base += "\n"
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=LOG_COLUMNS)
        for r in new_rows:
            writer.writerow(r)
        drive.write_text_file(logs_id, log_name, base + buf.getvalue())
    save_state(state, dry_run)

    done = sum(1 for r in new_rows
               if r["upload_status"] in ("uploaded", "dry-run", "already-existed"))
    dups = sum(1 for r in new_rows if r["duplicate_status"] == "duplicate")
    print(f"\nDone. {done} organized, {dups} duplicates skipped, "
          f"{len(new_rows) - done - dups} other/skipped. "
          f"Log: {root_name}/{cfg['logs_folder_name']}/{log_name}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test", action="store_true", help="process only 5 photos")
    ap.add_argument("--limit", type=int, help="process at most N photos")
    ap.add_argument("--full", action="store_true", help="no photo limit")
    ap.add_argument("--dry-run", action="store_true",
                    help="print planned actions; write nothing to OneDrive")
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
