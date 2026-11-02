"""Carousel posts: white Apple-style slides, 1080x1350, same footer (logo, contact, license) on every slide.

Slides come from Gemini as structured JSON (never HTML), so the brand frame stays fixed.
"""

import base64
import html
import re
from pathlib import Path

from .config import ROOT

ASSETS = ROOT / "assets"
ACCENTS = {
    "market_update": ("#0071E3", "#2AA8FF"),
    "seller_tip": ("#5E5CE6", "#AF52DE"),
    "buyer_tip": ("#1F9D55", "#34C759"),
    "town_spotlight": ("#E8590C", "#FF9F0A"),
    "community_life": ("#E8590C", "#FF9F0A"),
    "listing_spotlight": ("#0071E3", "#2AA8FF"),
}


def _b64(p):
    return base64.b64encode(Path(p).read_bytes()).decode()


def _fonts():
    out = ""
    for w, n in [("Regular", 400), ("Medium", 500), ("SemiBold", 600), ("Bold", 700), ("ExtraBold", 800), ("Black", 900)]:
        out += f"@font-face{{font-family:I;src:url(data:font/ttf;base64,{_b64(ASSETS / 'fonts' / f'Inter-{w}.ttf')});font-weight:{n}}}"
    return out


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:I;color:#1D1D1F;-webkit-font-smoothing:antialiased}
.s{width:1080px;height:1350px;position:relative;background:linear-gradient(#FFFFFF,#F5F5F7);padding:96px 96px 0;overflow:hidden}
.top{display:flex;justify-content:space-between;align-items:center;font-weight:600;font-size:30px}
.eb{color:var(--a)} .ct{color:#86868B;font-weight:500}
h1{font-weight:800;font-size:92px;line-height:1.02;letter-spacing:-3px;margin-top:56px}
h1 .g{color:#86868B;display:block}
h2{font-weight:800;font-size:76px;line-height:1.05;letter-spacing:-2.4px;margin-top:64px}
.big{font-weight:900;font-size:230px;line-height:1;letter-spacing:-10px;margin-top:56px;background:linear-gradient(90deg,var(--a),var(--a2));-webkit-background-clip:text;color:transparent;white-space:nowrap}
.big small{font-size:100px;letter-spacing:-3px}
.cap{font-size:40px;color:#6E6E73;font-weight:500;margin-top:18px;line-height:1.3}
.p{font-size:44px;line-height:1.36;color:#424245;font-weight:500;margin-top:40px;max-width:870px}
.p b{color:#1D1D1F;font-weight:700}
.cards{display:flex;gap:22px;margin-top:56px}
.card{flex:1;background:#fff;border-radius:34px;padding:38px 34px;box-shadow:0 10px 40px rgba(0,0,0,.06)}
.card .n{font-weight:800;font-size:70px;letter-spacing:-2px;color:var(--a)}
.card .l{font-size:30px;font-weight:600;margin-top:10px}
.card .d{font-size:26px;color:#86868B;margin-top:6px;line-height:1.3}
.list{margin-top:48px}
.row{display:flex;align-items:baseline;gap:28px;padding:26px 0;border-bottom:2px solid #E8E8ED}
.row .k{font-weight:800;font-size:54px;color:var(--a);min-width:300px;letter-spacing:-1.5px}
.row .v{font-size:36px;font-weight:500;color:#424245;line-height:1.3}
.chk .row .k{min-width:60px;font-size:44px}
.cta{margin-top:70px;display:inline-block;align-self:flex-start;background:#1D1D1F;color:#fff;font-weight:800;font-size:64px;padding:34px 56px;border-radius:999px;letter-spacing:-1px}
.cta span{color:var(--a2)}
.note{font-size:26px;color:#86868B;margin-top:34px;line-height:1.4;max-width:880px}
.body{position:absolute;left:96px;right:96px;top:150px;bottom:300px;display:flex;flex-direction:column;justify-content:center}
.body>*:first-child{margin-top:0}
.foot{position:absolute;left:96px;right:96px;bottom:40px;border-top:2px solid #E8E8ED;padding-top:24px}
.fr{display:flex;justify-content:space-between;align-items:center}
.foot .h{font-weight:700;font-size:34px}
.foot .c{font-size:26px;color:#424245;margin-top:6px}
.foot .lg{font-size:17.5px;color:#86868B;margin-top:8px;white-space:nowrap;letter-spacing:-.1px}
.one .big{font-size:170px;margin-top:30px}.one .cards{margin-top:36px}.one h1{font-size:84px}
.foot img{height:70px}
"""
CSS += ".big.m{font-size:170px;letter-spacing:-7px}.big.s{font-size:120px;letter-spacing:-4px}"


def e(s):
    return html.escape(str(s or ""))


def _big(v):
    v = str(v or "").strip()
    if not v:
        return ""
    size = "" if len(v) <= 5 else ("m" if len(v) <= 7 else "s")
    return f'<div class="big {size}">{e(v)}</div>'


def _rows(rows, check=False):
    out = '<div class="list chk">' if check else '<div class="list">'
    for r in rows or []:
        if isinstance(r, dict):
            r = [r.get("key") or r.get("k") or "", r.get("value") or r.get("v") or ""]
        if len(r) >= 2:
            out += f'<div class="row"><div class="k">{e(r[0])}</div><div class="v">{e(r[1])}</div></div>'
    return out + "</div>"


def slide_bodies(post):
    """Turn Gemini's carousel JSON into slide bodies (cover, content slides, recap, CTA)."""
    bodies = []
    bodies.append(f'<h1>{e(post["headline"])}<span class="g">{e(post.get("headline2", ""))}</span></h1>'
                  f'{_big(post.get("big"))}<div class="cap">{e(post.get("subhead", ""))}</div>')
    for s in post.get("slides", []):
        big, title, text = str(s.get("big") or "").strip(), s.get("title", ""), s.get("text", "")
        numbered = bool(re.fullmatch(r"\d{1,2}", big))
        if numbered:          # numbered slide: 01, 02...
            body = f'<div class="big">{e(big.zfill(2))}</div><h2>{e(title)}</h2>'
        else:
            body = f'<h2>{e(title)}</h2>{_big(big)}'
        if text:
            cls = "cap" if big and not numbered else "p"
            body += f'<div class="{cls}">{e(text)}</div>'
        if s.get("rows"):
            body += _rows(s["rows"], check=bool(s.get("checklist")))
        bodies.append(body)
    if post.get("recap"):
        bodies.append(f'<h2>{e(post.get("recap_title", "On one slide"))}</h2>{_rows(post["recap"])}')
    bodies.append(f'<h2>{e(post.get("cta_title", "Want the numbers?"))}</h2><div class="p">{e(post.get("cta_text", ""))}</div>'
                  f'<div class="cta">Comment <span>{e(post.get("cta_keyword", "VALUE"))}</span></div>')
    return bodies


def _foot(src):
    s = f'<div class="lg">Source: {e(src)}</div>' if src else ""
    return (f'<div class="foot"><div class="fr"><div><div class="h">@jaskaranrealtor</div>'
            f'<div class="c">Call/Text (475) 400-0661 · jaskaranrealtor.com</div>'
            f'<div class="c">English · Hindi · Punjabi · Urdu</div></div>'
            f'<img src="data:image/png;base64,{_b64(ASSETS / "logos" / "logo_black.png")}"></div>{s}'
            f'<div class="lg">Jaskaran Singh, REALTOR® · Brokered by Vylla Home · CT Lic# RES.0820095 · '
            f'Equal Housing Opportunity</div></div>')


def render_slides(bodies, eyebrow, theme, out_dir, prefix="slide", source=None):
    """Render slide bodies to 1080x1350 JPGs. Returns the file paths in order."""
    from PIL import Image
    from playwright.sync_api import sync_playwright
    a, a2 = ACCENTS.get(theme, ACCENTS["market_update"])
    n = len(bodies)
    foot = _foot(source)
    pages = ""
    for i, body in enumerate(bodies, 1):
        cls, ctr = ("s one", "") if n == 1 else ("s", f"{i}/{n}")
        pages += (f'<div class="{cls}" style="--a:{a};--a2:{a2}"><div class="top"><span class="eb">{e(eyebrow)}</span>'
                  f'<span class="ct">{ctr}</span></div><div class="body">{body}</div>{foot}</div>')
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350})
        page.set_content(f"<html><head><meta charset=utf-8><style>{_fonts()}{CSS}</style></head><body>{pages}</body></html>")
        page.wait_for_timeout(300)
        for i, el in enumerate(page.query_selector_all(".s"), 1):
            png = out_dir / f"{prefix}-{i:02d}.png"
            el.screenshot(path=str(png))
            jpg = png.with_suffix(".jpg")
            Image.open(png).convert("RGB").save(jpg, quality=92, subsampling=0)
            png.unlink()
            files.append(jpg)
        browser.close()
    return files
