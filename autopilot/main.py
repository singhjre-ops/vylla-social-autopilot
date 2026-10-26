"""Social autopilot.

  python -m autopilot.main week              build next week's posts as a Metricool CSV (free plan)
  python -m autopilot.main voices            pick up your Telegram voice notes and rebuild those videos

  python -m autopilot.main generate          make today's draft and send it for approval
  python -m autopilot.main publish           post today's draft once approved and past post time
  python -m autopilot.main approve|skip       decide on today's draft without Telegram
  python -m autopilot.main accounts          list social accounts connected in Zernio
  python -m autopilot.main generate --sample no Gemini key needed; uses a canned post (for testing)
"""

import argparse
import csv
import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import audio, compliance, gemini, metricool, motion, telegram
from .config import DATA, QUEUE, load_config, load_env
from .publishers import list_zernio_accounts, publish
from .render import make_video, render
from .themes import THEMES

SAMPLE = {
    "headline": "Fall on Lake Zoar in Southbury",
    "subhead": "Trails, foliage drives and weekend farm stands, all close to home.",
    "caption": "October is a great month to explore Southbury. Kettletown State Park trails run along Lake Zoar, "
               "and back roads light up with color. If you're thinking about a move in the area this season, "
               "I'm happy to walk you through what's on the market. Send me a message any time.",
    "short_caption": "Fall color along Lake Zoar in Southbury. Thinking about a move this season? Let's talk.",
    "hashtags": ["SouthburyCT", "LakeZoar", "CTRealEstate", "LitchfieldHills", "FallInCT"],
    "voiceover": "Fall in Southbury means Lake Zoar trails and bright back roads. Thinking about a move? "
                 "Call or text Jaskaran Singh with Vylla Home.",
    "hook": "Southbury in four quick facts.",
    "hook_say": "Here's Southbury in four quick facts.",
    "scenes": [
        {"label": "Outdoors", "title": "Kettletown State Park", "detail": "Hiking trails and a swim area on the shore of Lake Zoar.",
         "say": "Kettletown State Park puts trails and a swim beach right on Lake Zoar."},
        {"label": "Commute", "title": "Right off I-84", "detail": "Highway access toward Danbury and Waterbury.",
         "say": "You're right off I-84, so Danbury and Waterbury are an easy drive."},
        {"label": "Town center", "title": "Main Street South", "detail": "Shops, dining and the town green along Route 6.",
         "say": "Main Street South has the shops, the dining and the town green."},
        {"label": "Seasonal", "title": "Fall back roads", "detail": "Farm stands and foliage drives through the Pomperaug valley.",
         "say": "And in the fall, the back roads and farm stands are hard to beat."},
    ],
    "cta_line": "Want the numbers on a Southbury home?",
}


def _rows(name):
    with open(DATA / name, newline="") as f:
        return [r for r in csv.DictReader(f) if any(r.values())]


def _posted_ids():
    ids = set()
    for p in QUEUE.glob("*/post.json"):
        ids.add(json.loads(p.read_text()).get("source_id"))
    return ids


def pick(cfg, today):
    """Choose theme, town and facts for today. Falls back when data is missing."""
    theme = cfg["calendar"][today.weekday()]
    regions = list(cfg["regions"].values())
    day = today.toordinal()
    towns = regions[day % len(regions)]  # next region each day
    town = towns[(day // len(regions)) % len(towns)]
    facts = {"town": town, "month": today.strftime("%B")}

    if theme == "listing_spotlight":
        agent_id = cfg["agent"]["smart_mls_agent_id"]
        listings = [r for r in _rows("listings.csv")
                    if r["status"].lower() == "active"
                    and r["seller_consent"].lower() in ("yes", "y", "true")
                    and (not agent_id or r["list_agent_id"] == agent_id)
                    and r["mls_number"] not in _posted_ids()]
        if listings:
            l = listings[0]
            facts.update(town=l["town"], address=l["address"], photo_url=l["photo_url"], source_id=l["mls_number"],
                         listing=f"${int(float(l['price'])):,}, {l['beds']} bed, {l['baths']} bath, "
                                 f"{l['sqft']} sq ft. {l['highlights']}")
        else:
            theme = "buyer_tip"

    if theme == "market_update":
        stats = _rows("market_stats.csv")
        if stats:
            latest = max(r["month"] for r in stats)
            month_rows = [r for r in stats if r["month"] == latest]
            row = month_rows[today.toordinal() % len(month_rows)]
            facts.update(town=row["town"], source_id=f"stats-{latest}-{row['town']}",
                         stats=f"{latest}: median sale price ${int(float(row['median_sale_price'])):,}, "
                               f"{row['closed_sales']} closed sales, {row['median_days_on_market']} median days "
                               f"on market, {row['active_inventory']} active listings (source: {row['source']})")
        else:
            theme = "town_spotlight"  # never let AI guess market numbers

    return theme, facts


def generate(cfg, today, sample=False, notify=True):
    post_id = today.isoformat()
    out = QUEUE / post_id
    out.mkdir(parents=True, exist_ok=True)
    theme, facts = pick(cfg, today)
    brief = THEMES[theme]["brief"].format(**{k: facts.get(k, "") for k in
                                             ("town", "month", "stats", "address", "listing")})

    # Retry up to 3 times if the compliance check finds a problem.
    for attempt in range(3):
        post = dict(SAMPLE) if sample else gemini.generate(cfg, brief)
        problems = compliance.check(post, cfg)
        if not problems:
            break
        print(f"attempt {attempt + 1} flagged: {problems}")
        brief += "\nAvoid these phrases: " + "; ".join(problems)
    if sample:
        facts["town"] = "Southbury"

    post["captions"] = compliance.finalize(post, cfg)
    post.update(id=post_id, theme=theme, town=facts["town"], source_id=facts.get("source_id"),
                problems=problems, status="pending")

    label = THEMES[theme]["label"]
    render(post, label, facts["town"], cfg, out / "feed.jpg", photo_url=facts.get("photo_url"))
    render(post, label, facts["town"], cfg, out / "vertical.jpg", size=(1080, 1920), photo_url=facts.get("photo_url"))
    has_scenes = isinstance(post.get("scenes"), list) and len(post["scenes"]) >= 2 and \
        all(isinstance(sc, dict) and sc.get("title") for sc in post["scenes"])
    if has_scenes:
        post.setdefault("hook", post["headline"])
        post.setdefault("cta_line", f"Want the numbers on a {facts['town']} home?")
        post["cta_keyword"] = cfg.get("video", {}).get("cta_keyword", "VALUE")
        post["cta_say"] = cfg.get("video", {}).get("cta_say", "Call or text me, Jaskaran Singh, with Vylla Home.")
        post["voiceover"] = motion.spoken_script(post)
    voice, post["voice_source"] = None, "none"
    try:
        voice = audio.voiceover(cfg, post.get("voiceover"), out / "voice.wav")
        post["voice_source"] = "ai" if voice else "none"
    except Exception as e:  # never let audio break the post
        print(f"voiceover failed: {e}")
    music = audio.pick_music(today.toordinal())
    vol = cfg.get("music", {}).get("volume", 0.15)
    if has_scenes:
        motion.render_motion(post, out / "vertical.mp4", voice=voice, music=music, music_volume=vol)
    else:
        make_video(out / "vertical.jpg", out / "vertical.mp4", voice=voice, music=music, music_volume=vol)
    credit = audio.music_credit(music)
    if credit:  # CC BY license: credit the artist wherever the video is posted
        post["music_credit"] = credit
        for k in ("long", "short"):
            post["captions"][k] += f"\n\n{credit}"

    # A post that still has flags always waits for you, even in full-auto mode.
    if not notify:
        pass  # weekly Metricool batch: you review in Metricool's calendar
    elif cfg["approval_required"] or problems:
        if os.environ.get("TELEGRAM_BOT_TOKEN"):
            telegram.send_draft(post_id, out / "feed.jpg", post["captions"], problems)
        else:
            print(f"Telegram not set up. Review {out} then run: python -m autopilot.main approve")
    else:
        post["status"] = "approved"
    (out / "post.json").write_text(json.dumps(post, indent=2))
    print(f"draft {post_id}: {theme} / {facts['town']} -> {post['status']}")
    return out


def publish_due(cfg, now):
    post_dir = QUEUE / now.date().isoformat()
    path = post_dir / "post.json"
    if not path.exists():
        print("no draft for today")
        return
    post = json.loads(path.read_text())
    if post["status"] in ("posted", "skipped"):
        print(f"already {post['status']}")
        return
    if post["status"] == "pending" and os.environ.get("TELEGRAM_BOT_TOKEN"):
        decision = telegram.get_decision(post["id"])
        if decision == "skip":
            post["status"] = "skipped"
        elif decision == "approve":
            post["status"] = "approved"
        path.write_text(json.dumps(post, indent=2))
    if post["status"] != "approved":
        print(f"status {post['status']}; nothing to post")
        return
    hh, mm = map(int, cfg["post_time_local"].split(":"))
    if (now.hour, now.minute) < (hh, mm):
        print(f"approved; waiting for {cfg['post_time_local']}")
        return
    post["result"] = publish(cfg, post_dir, post)
    post["status"] = "posted"
    path.write_text(json.dumps(post, indent=2))
    partial = [r for r in post["result"] if isinstance(r, dict) and r.get("status") == 207] \
        if isinstance(post["result"], list) else []
    note = " ⚠️ Some platforms failed; check post.json." if partial else ""
    telegram.notify(f"Posted {post['id']}: {post['headline']}{note}")
    print("posted")


def build_week(cfg, today, sample=False):
    """Make next Monday-Sunday's posts and a Metricool CSV to import."""
    week_start = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
    out, rows, skipped, ledger = metricool.build_week(
        cfg, week_start, lambda day: generate(cfg, day, sample=sample, notify=False))
    metricool.prune_media(today)
    summary = (f"Metricool CSV for week of {week_start}: {len(rows)} posts. "
               f"Used this month: {json.dumps(ledger)} of {cfg['metricool']['monthly_post_limit']}.")
    if skipped:
        summary += f" Skipped to stay under the limit: {', '.join(skipped)}."
    print(summary)
    print(out)
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        video_days = send_scripts(cfg, week_start)
        note = ("\nRecord your voice first (scripts below), then import this file. "
                "If you skip a script, that video keeps the AI voice.") if video_days else ""
        telegram.send_document(out, summary + note + "\nImport it in Metricool: Calendar > Import CSV.")


def _week_video_dirs(cfg, week_start):
    dirs = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        nets = cfg["metricool"]["schedule"].get(day.weekday())
        d = QUEUE / day.isoformat()
        if nets and "gmb" not in nets and (d / "post.json").exists():
            post = json.loads((d / "post.json").read_text())
            if post.get("scenes"):
                dirs.append((day, d, post))
    return dirs


def send_scripts(cfg, week_start):
    """Send each video's script to Telegram. Reply to a script with a voice note to use your own voice."""
    dirs = _week_video_dirs(cfg, week_start)
    if not dirs:
        return []
    telegram.send_text(
        f"🎙 Your scripts for the week of {week_start:%b %d}. For each one: tap Reply, hold the mic, "
        "read it naturally (about 15-20 seconds), send. I'll rebuild that video with your voice within "
        "about 30 minutes. Quiet room, phone 6 inches from your mouth.")
    for day, d, post in dirs:
        text = (f"{day:%a %b %d} · {post['town']}\n\n" + motion.spoken_script(post) +
                "\n\n↩️ Reply to this message with your voice note.")
        post["script_msg_id"] = telegram.send_text(text)
        (d / "post.json").write_text(json.dumps(post, indent=2))
    return [day for day, _, _ in dirs]


def _clean_voice(src, dest):
    """Trim silence at both ends, cut rumble, even out loudness."""
    import subprocess
    af = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.15,areverse,"
          "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.2,areverse,"
          "highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", af, "-ar", "48000", "-ac", "1",
                    str(dest)], check=True)
    return dest


def rebuild_with_voice(cfg, day, d, post):
    voice = d / "my_voice.wav"
    music = audio.pick_music(day.toordinal())
    motion.render_motion(post, d / "vertical.mp4", voice=voice, music=music,
                         music_volume=cfg.get("music", {}).get("volume", 0.15))
    media = metricool.MEDIA_DIR / f"{day.isoformat()}.mp4"
    if media.parent.exists():
        import shutil
        shutil.copy(d / "vertical.mp4", media)
    post["voice_source"] = "jaskaran"
    (d / "post.json").write_text(json.dumps(post, indent=2))


def process_voices(cfg):
    """Pick up voice notes sent to the bot and rebuild the matching videos."""
    state_file = DATA / "telegram_state.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {"offset": 0}
    msgs, state["offset"] = telegram.get_messages(state.get("offset", 0))
    pending = {}
    for p in sorted(QUEUE.glob("*/post.json")):
        post = json.loads(p.read_text())
        if post.get("script_msg_id"):
            pending[post["script_msg_id"]] = (datetime.fromisoformat(post["id"]).date(), p.parent, post)
    done = []
    for m in msgs:
        media = m.get("voice") or m.get("audio") or m.get("video_note")
        if not media:
            continue
        target = pending.get((m.get("reply_to_message") or {}).get("message_id"))
        if not target:  # not a reply: use it for the earliest script still on the AI voice
            open_ones = [v for v in pending.values() if v[2].get("voice_source") != "jaskaran"
                         and v[0] >= datetime.now(ZoneInfo(cfg["timezone"])).date()]
            target = min(open_ones, key=lambda v: v[0]) if open_ones else None
        if not target:
            telegram.send_text("I couldn't tell which script that voice note was for. "
                               "Please reply directly to the script message.", reply_to=m["message_id"])
            continue
        day, d, post = target
        raw = telegram.download(media["file_id"], d / "my_voice_raw.ogg")
        _clean_voice(raw, d / "my_voice.wav")
        raw.unlink(missing_ok=True)
        rebuild_with_voice(cfg, day, d, post)
        done.append(day)
        left = [v for v in pending.values() if v[2].get("voice_source") != "jaskaran" and v[0] >= day - timedelta(days=7)]
        telegram.send_text(f"✅ Got it: {day:%a %b %d} ({post['town']}) now uses your voice. "
                           + (f"{len(left)} script(s) left." if left else "All scripts done."),
                           reply_to=m["message_id"])
    state_file.write_text(json.dumps(state, indent=2))
    if done:
        week_start = min(done) - timedelta(days=min(done).weekday())
        csv_path = metricool.EXPORTS / f"metricool-week-{week_start.isoformat()}.csv"
        if csv_path.exists():
            telegram.send_document(csv_path, "Videos updated with your voice. Give it ~2 minutes to go live, "
                                             "then import this file in Metricool (delete any drafts you "
                                             "imported before recording).")
    print(f"voices processed: {[d.isoformat() for d in done]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["week", "generate", "publish", "approve", "skip", "accounts", "voices"])
    parser.add_argument("--sample", action="store_true", help="use a canned post instead of Gemini")
    parser.add_argument("--date", help="YYYY-MM-DD, defaults to today")
    args = parser.parse_args()

    load_env()
    cfg = load_config()
    now = datetime.now(ZoneInfo(cfg["timezone"]))
    if args.date:
        now = now.replace(**dict(zip(("year", "month", "day"), map(int, args.date.split("-")))))
    if args.command == "week":
        build_week(cfg, now.date(), sample=args.sample)
    elif args.command == "generate":
        generate(cfg, now.date(), sample=args.sample)
    elif args.command == "publish":
        publish_due(cfg, now)
    elif args.command == "voices":
        process_voices(cfg)
    elif args.command == "accounts":
        list_zernio_accounts()
    else:
        path = QUEUE / now.date().isoformat() / "post.json"
        post = json.loads(path.read_text())
        post["status"] = "approved" if args.command == "approve" else "skipped"
        path.write_text(json.dumps(post, indent=2))
        print(f"{post['id']} {post['status']}")


if __name__ == "__main__":
    main()
