"""Build a week of posts as a Metricool CSV import, without going over the monthly post limit.

Metricool: Planning -> Calendar -> options menu -> Import CSV.
For exact column names, download Metricool's template there once and save it as
data/metricool_template.csv. Columns are matched by name, so the template's own
wording and order win. Without it, a best-guess English header is used.
"""

import csv
import json
import re
import shutil
from datetime import date, timedelta

from .config import DATA, ROOT

MEDIA_DIR = ROOT / "docs" / "media"
EXPORTS = ROOT / "exports"
LEDGER = DATA / "metricool_ledger.json"

NETWORKS = ["facebook", "twitter", "linkedin", "gmb", "instagram", "pinterest", "tiktok", "youtube",
            "threads", "bluesky"]
DEFAULT_HEADER = ["Text", "Date", "Time", "Draft", "Facebook", "Twitter", "LinkedIn", "GMB", "Instagram",
                  "Pinterest", "TikTok", "Youtube", "Threads", "Bluesky", "Picture Url 1",
                  "Youtube Video Title", "Youtube Video For Kids", "TikTok Title", "Brand name",
                  "Instagram Post Type", "Instagram Show Reel On Feed", "Facebook Post Type",
                  "YouTube Video Type", "YouTube Video Privacy"]
ALIASES = {"gmb": ("gmb", "gbp", "googlebusiness", "googlemybusiness"), "twitter": ("twitter", "twitterx", "x")}


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _header():
    template = DATA / "metricool_template.csv"
    if template.exists():
        with open(template, newline="", encoding="utf-8-sig") as f:
            return next(csv.reader(f))
    return DEFAULT_HEADER


def _column(header, key):
    """Find the template column for a field, whatever Metricool currently calls it."""
    for col in header:
        n = _norm(col)
        if key in NETWORKS and n in ALIASES.get(key, (key,)):
            return col
        if key in ("text", "date", "time", "draft") and n == key:
            return col
        if key == "media" and n.endswith("url1") and ("picture" in n or "image" in n or "media" in n):
            return col
        if key == "youtube_title" and n.startswith("youtube") and "title" in n:
            return col
        if key == "youtube_kids" and n.startswith("youtube") and "kids" in n:
            return col
        if key == "tiktok_title" and n.startswith("tiktok") and "title" in n:
            return col
        if key == "ig_type" and n == "instagramposttype":
            return col
        if key == "ig_feed" and n == "instagramshowreelonfeed":
            return col
        if key == "fb_type" and n == "facebookposttype":
            return col
        if key == "yt_type" and n == "youtubevideotype":
            return col
        if key == "yt_privacy" and n == "youtubevideoprivacy":
            return col
    return None


def _ledger():
    """Posts scheduled per day, e.g. {"2026-10-20": 1}. Keyed by day so rebuilding a week never double-counts."""
    return json.loads(LEDGER.read_text()) if LEDGER.exists() else {}


def month_totals(ledger):
    totals = {}
    for day, cost in ledger.items():
        totals[day[:7]] = totals.get(day[:7], 0) + cost
    return totals


def build_week(cfg, week_start, generate):
    """Generate posts for the 7 days from week_start and write a Metricool CSV.

    `generate(day)` makes one day's post and returns its queue folder.
    """
    mc = cfg["metricool"]
    header = _header()
    ledger = _ledger()
    rows, skipped = [], []
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    base = mc["media_base_url"].rstrip("/")

    for offset in range(7):
        day = week_start + timedelta(days=offset)
        networks = mc["schedule"].get(day.weekday())
        if not networks:
            continue
        ledger.pop(day.isoformat(), None)  # rebuilding this day replaces its old count
        cost = 1 if mc["count_mode"] == "per_row" else len(networks)
        if month_totals(ledger).get(day.strftime("%Y-%m"), 0) + cost > mc["monthly_post_limit"]:
            skipped.append(day.isoformat())
            continue

        post_dir = generate(day)
        post = json.loads((post_dir / "post.json").read_text())
        video = "gmb" not in networks and (post_dir / "vertical.mp4").exists()
        src = post_dir / ("vertical.mp4" if video else "feed.jpg")
        media_name = f"{day.isoformat()}{src.suffix}"
        shutil.copy(src, MEDIA_DIR / media_name)

        values = {
            "text": post["captions"]["gmb" if networks == ["gmb"] else "long"],
            "date": day.isoformat(),
            "time": cfg["post_time_local"] + ":00",
            "draft": "TRUE" if mc["import_as_draft"] else "FALSE",
            "media": f"{base}/{media_name}",
            "youtube_title": post["headline"][:100] if "youtube" in networks else "",
            "youtube_kids": "FALSE" if "youtube" in networks else "",
            # TikTok Title applies to photo posts only
            "tiktok_title": post["headline"][:90] if "tiktok" in networks and not video else "",
            # Instagram rejects a single video as a feed POST: videos go out as Reels (also shown on the feed)
            "ig_type": ("REEL" if video else "POST") if "instagram" in networks else "",
            "ig_feed": "TRUE" if video and "instagram" in networks else "",
            "fb_type": ("REEL" if video else "POST") if "facebook" in networks else "",
            "yt_type": "SHORT" if "youtube" in networks else "",
            "yt_privacy": "PUBLIC" if "youtube" in networks else "",
        }
        for n in NETWORKS:
            values[n] = "TRUE" if n in networks else "FALSE"
        row = {col: "" for col in header}
        for key, value in values.items():
            col = _column(header, key)
            if col:
                row[col] = value
            elif value and value != "FALSE" and key != "youtube_kids":
                raise ValueError(f"Metricool template has no column for {key}")
        if post.get("problems"):
            row[_column(header, "draft")] = "TRUE"  # flagged posts always wait for you
        rows.append(row)
        ledger[day.isoformat()] = cost

    EXPORTS.mkdir(exist_ok=True)
    out = EXPORTS / f"metricool-week-{week_start.isoformat()}.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    LEDGER.write_text(json.dumps(ledger, indent=2, sort_keys=True))
    return out, rows, skipped, month_totals(ledger)


def prune_media(today, keep_days=30):
    """Delete hosted media more than keep_days past its post date, so the site stays small."""
    for f in MEDIA_DIR.glob("*.*"):
        try:
            post_day = date.fromisoformat(f.stem)
        except ValueError:
            continue
        if (today - post_day).days > keep_days:
            f.unlink()
