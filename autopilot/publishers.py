"""Send approved posts to social platforms.

dryrun prints what would be posted. zernio (about $6 per account a month) and ayrshare
(about $149 a month) each post to Facebook, Instagram, Google Business Profile, X, TikTok
and YouTube through one API.
"""

import base64
import json
import os

import requests

VIDEO_PLATFORMS = {"tiktok", "youtube"}


def publish(cfg, post_dir, post):
    kind = cfg["publisher"]
    groups = _groups(cfg["platforms"], post, post_dir)
    if kind == "dryrun":
        for g in groups:
            print(f"[dryrun] {', '.join(g['platforms'])}: {g['media'].name}\n{g['text']}\n")
        return {"dryrun": True}
    if kind == "zernio":
        accounts = _zernio_accounts()
        return [_zernio(g, post, accounts, cfg) for g in groups]
    if kind == "ayrshare":
        return [_ayrshare(g, post) for g in groups]
    raise ValueError(f"unknown publisher: {kind}")


def _groups(platforms, post, post_dir):
    """Each platform group gets the caption length and media type it needs."""
    caps = post["captions"]
    feed, video = post_dir / "feed.jpg", post_dir / "vertical.mp4"
    groups = [
        {"platforms": [p for p in platforms if p in ("facebook", "instagram")], "text": caps["long"], "media": feed},
        {"platforms": [p for p in platforms if p == "gmb"], "text": caps["gmb"], "media": feed},
        {"platforms": [p for p in platforms if p == "twitter"], "text": caps["short"], "media": feed},
    ]
    if video.exists():
        groups.append({"platforms": [p for p in platforms if p in VIDEO_PLATFORMS],
                       "text": caps["short"], "media": video})
    return [g for g in groups if g["platforms"]]


def _ayrshare(group, post):
    key = os.environ["AYRSHARE_API_KEY"]
    headers = {"Authorization": f"Bearer {key}"}
    media = group["media"]
    mime = "video/mp4" if media.suffix == ".mp4" else "image/jpeg"
    upload = requests.post(
        "https://api.ayrshare.com/api/media/upload", headers=headers, timeout=120,
        json={"file": f"data:{mime};base64,{base64.b64encode(media.read_bytes()).decode()}",
              "fileName": media.name},
    )
    upload.raise_for_status()
    body = {"post": group["text"], "platforms": group["platforms"], "mediaUrls": [upload.json()["url"]]}
    if media.suffix == ".mp4":
        body["isVideo"] = True
        if "youtube" in group["platforms"]:
            body["youTubeOptions"] = {"title": post["headline"][:100], "shorts": True, "visibility": "public"}
    resp = requests.post("https://api.ayrshare.com/api/post", headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    return resp.json()


# Zernio (https://zernio.com, formerly Late). Docs: https://docs.zernio.com
ZERNIO = "https://zernio.com/api/v1"
ZERNIO_NAMES = {"gmb": "googlebusiness"}  # config name -> Zernio platform name


def _zernio_headers():
    return {"Authorization": f"Bearer {os.environ['ZERNIO_API_KEY']}"}


def _zernio_accounts():
    """Map platform name -> account id for every account connected in Zernio."""
    resp = requests.get(f"{ZERNIO}/accounts", headers=_zernio_headers(), timeout=60)
    resp.raise_for_status()
    return {a["platform"]: a["_id"] for a in resp.json()["accounts"]}


def _zernio(group, post, accounts, cfg):
    media = group["media"]
    mime = "video/mp4" if media.suffix == ".mp4" else "image/jpeg"
    presign = requests.post(f"{ZERNIO}/media/presign", headers=_zernio_headers(), timeout=60,
                            json={"filename": f"{post['id']}-{media.name}", "contentType": mime,
                                  "size": media.stat().st_size})
    presign.raise_for_status()
    urls = presign.json()
    requests.put(urls["uploadUrl"], data=media.read_bytes(), headers={"Content-Type": mime},
                 timeout=300).raise_for_status()

    platforms = []
    for name in group["platforms"]:
        zname = ZERNIO_NAMES.get(name, name)
        if zname not in accounts:
            print(f"zernio: no connected {zname} account; skipping")
            continue
        entry = {"platform": zname, "accountId": accounts[zname]}
        if zname == "googlebusiness":
            entry["platformSpecificData"] = {
                "callToAction": {"type": "LEARN_MORE", "url": f"https://{cfg['agent']['website']}"}}
        if zname == "youtube":
            entry["platformSpecificData"] = {"title": post["headline"][:100], "visibility": "public",
                                             "madeForKids": False}
        platforms.append(entry)
    if not platforms:
        return {"skipped": group["platforms"]}

    body = {"content": group["text"], "mediaItems": [{"url": urls["publicUrl"],
                                                      "type": "video" if mime == "video/mp4" else "image"}],
            "platforms": platforms, "publishNow": True}
    if any(p["platform"] == "tiktok" for p in platforms):
        # TikTok requires these on every API post.
        body["tiktokSettings"] = {"privacy_level": "PUBLIC_TO_EVERYONE", "allow_comment": True,
                                  "allow_duet": False, "allow_stitch": False,
                                  "content_preview_confirmed": True, "express_consent_given": True}
    resp = requests.post(f"{ZERNIO}/posts", headers=_zernio_headers(), json=body, timeout=300)
    resp.raise_for_status()
    result = resp.json()
    # 207 means some platforms failed; report it instead of treating it as success.
    if resp.status_code == 207:
        print(f"zernio: partial publish: {json.dumps(result.get('platformResults'))}")
    return {"status": resp.status_code, "post": result.get("post", {}).get("_id"),
            "platformResults": result.get("platformResults")}


def list_zernio_accounts():
    for platform, account_id in _zernio_accounts().items():
        print(f"{platform:16} {account_id}")
