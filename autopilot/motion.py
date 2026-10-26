"""Animated explainer videos: white, Apple-style type, a 3D house hook, scene-by-scene info.

render_motion(post, out_path, cfg, voice=None, music=None)

post needs: town, hook, scenes=[{label, title, detail, say}], hook_say, cta_say, cta_keyword
Frames are drawn with Pillow and piped straight into ffmpeg; audio is mixed in a second pass.
"""
import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    from .config import ASSETS
except ImportError:  # standalone testing
    ASSETS = Path(__file__).resolve().parent / "assets"

W, H, FPS = 1080, 1920, 30
INK = (29, 29, 31)
SUB = (110, 110, 115)
FAINT = (232, 232, 237)
BG_TOP, BG_BOT = (255, 255, 255), (245, 245, 247)
GOLD = (255, 176, 0)
CHAR = (49, 49, 59)
SAFE_X = 96


def font(weight, size):
    p = ASSETS / "fonts" / f"Inter-{weight}.ttf"
    if not p.exists():
        p = ASSETS / "fonts" / ("Roboto-Bold.ttf" if weight in ("Bold", "ExtraBold", "Black", "SemiBold") else "Roboto-Light.ttf")
    return ImageFont.truetype(str(p), size)


# ---------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = clamp(t)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_back(t):
    t = clamp(t)
    c1, c3 = 1.4, 2.4
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


# ---------------------------------------------------------------- text helpers
def wrap(d, text, f, width):
    lines, cur = [], ""
    for w in str(text).split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= width:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def text_block(img, x, y, text, f, fill, width, t, lh=1.15, stagger=0.12, rise=40, center=False):
    """Draw wrapped text, each line fading and rising in, staggered. t = local time in seconds."""
    d = ImageDraw.Draw(img)
    lines = wrap(d, text, f, width)
    for i, line in enumerate(lines):
        p = ease_out((t - i * stagger) / 0.45)
        if p <= 0:
            y += int(f.size * lh)
            continue
        layer = Image.new("RGBA", (W, int(f.size * 1.6)), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        lx = (W - ld.textlength(line, font=f)) / 2 if center else x
        ld.text((lx, 0), line, font=f, fill=fill + (int(255 * p),))
        img.alpha_composite(layer, (0, int(y + rise * (1 - p))))
        y += int(f.size * lh)
    return y


def pill(img, x, y, text, t, fill=GOLD, fg=INK, size=34):
    p = ease_back(t / 0.5)
    if p <= 0:
        return
    f = font("Bold", size)
    d = ImageDraw.Draw(img)
    tw = d.textlength(text, font=f)
    w, h = tw + 48, size + 30
    layer = Image.new("RGBA", (int(w) + 4, int(h) + 4), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rounded_rectangle([0, 0, w, h], radius=h / 2, fill=fill)
    ld.text((24, h / 2), text, font=f, fill=fg, anchor="lm")
    s = max(0.01, p)
    layer = layer.resize((max(1, int(layer.width * s)), max(1, int(layer.height * s))))
    img.alpha_composite(layer, (int(x), int(y + (h - layer.height) / 2)))


# ---------------------------------------------------------------- background
_BG = None


def background():
    global _BG
    if _BG is None:
        bg = Image.new("RGBA", (W, H))
        d = ImageDraw.Draw(bg)
        for y in range(H):
            k = y / H
            d.line([0, y, W, y], fill=tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * k) for i in range(3)) + (255,))
        _BG = bg
    return _BG.copy()


# ---------------------------------------------------------------- 3D house
def _house_mesh():
    """Vertices and coloured faces for a simple house: walls, gable roof, chimney, door, windows."""
    w, d, h, r = 1.0, 0.8, 0.75, 0.55
    V = {
        "a": (-w, 0, -d), "b": (w, 0, -d), "c": (w, 0, d), "e": (-w, 0, d),
        "A": (-w, h, -d), "B": (w, h, -d), "C": (w, h, d), "E": (-w, h, d),
        "R1": (-w, h + r, 0), "R2": (w, h + r, 0),
    }
    wall, wall2, roof, roof2 = (246, 242, 236), (232, 227, 220), (49, 49, 59), (66, 66, 78)
    faces = [
        (["a", "b", "B", "A"], wall),       # back
        (["c", "e", "E", "C"], wall),       # front
        (["e", "a", "A", "E"], wall2),      # left
        (["b", "c", "C", "B"], wall2),      # right
        (["A", "B", "R2", "R1"], roof),     # roof back
        (["C", "E", "R1", "R2"], roof2),    # roof front
        (["E", "A", "R1"], wall2),          # gable left
        (["B", "C", "R2"], wall2),          # gable right
    ]
    # door + windows on the front face (z = d), slightly proud of the wall
    z = d + 0.004
    def quad(x0, x1, y0, y1, col):
        k = f"q{len(faces)}"
        V[k + "1"], V[k + "2"], V[k + "3"], V[k + "4"] = (x0, y0, z), (x0, y1, z), (x1, y1, z), (x1, y0, z)
        faces.append(([k + "4", k + "3", k + "2", k + "1"], col))
    quad(-0.16, 0.16, 0.0, 0.46, GOLD)                # door in Vylla gold
    quad(-0.78, -0.42, 0.30, 0.58, (150, 196, 230))   # windows
    quad(0.42, 0.78, 0.30, 0.58, (150, 196, 230))
    # chimney
    cx0, cx1, cz0, cz1, cy0, cy1 = 0.45, 0.62, -0.35, -0.18, h + 0.15, h + 0.75
    for n, p in zip("12345678", [(cx0, cy0, cz0), (cx1, cy0, cz0), (cx1, cy0, cz1), (cx0, cy0, cz1),
                                 (cx0, cy1, cz0), (cx1, cy1, cz0), (cx1, cy1, cz1), (cx0, cy1, cz1)]):
        V["ch" + n] = p
    ch = (120, 72, 60)
    faces += [(["ch1", "ch2", "ch6", "ch5"], ch), (["ch3", "ch4", "ch8", "ch7"], ch),
              (["ch4", "ch1", "ch5", "ch8"], ch), (["ch2", "ch3", "ch7", "ch6"], ch),
              (["ch5", "ch6", "ch7", "ch8"], (90, 54, 45))]
    return V, faces


MESH = _house_mesh()


def render_house(angle_deg, size=760, tilt_deg=20, scale=1.0):
    """Flat-shaded 3D house, transparent background, drawn at 2x and downsampled for smooth edges."""
    V, faces = MESH
    ss = 2
    S = size * ss
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    a, tl = math.radians(angle_deg), math.radians(tilt_deg)
    ca, sa, ct, st = math.cos(a), math.sin(a), math.cos(tl), math.sin(tl)
    cam, f = 5.2, S * 1.45 * scale
    light = (-0.45, 0.75, 0.5)
    ln = math.sqrt(sum(c * c for c in light))
    light = tuple(c / ln for c in light)

    def tf(p):
        x, y, z = p
        y -= 0.75
        x, z = x * ca + z * sa, -x * sa + z * ca           # rotate about Y
        y, z = y * ct - z * st, y * st + z * ct            # tilt about X
        return x, y, z

    def proj(p):
        x, y, z = p
        k = f / (cam - z)
        return S / 2 + x * k, S / 2 - y * k

    # ground shadow
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    gx, gy = proj(tf((0, 0, 0)))
    sd.ellipse([gx - S * 0.30 * scale, gy - S * 0.045, gx + S * 0.30 * scale, gy + S * 0.045], fill=(0, 0, 0, 60))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(S * 0.02)))

    polys = []
    center = tf((0, 0.62, 0))
    for idx, col in faces:
        P = [tf(V[k]) for k in idx]
        (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = P[0], P[1], P[2]
        ux, uy, uz = x2 - x1, y2 - y1, z2 - z1
        vx, vy, vz = x3 - x1, y3 - y1, z3 - z1
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        nl = math.sqrt(nx * nx + ny * ny + nz * nz) or 1
        nx, ny, nz = nx / nl, ny / nl, nz / nl
        cx = sum(p[0] for p in P) / len(P)
        cy = sum(p[1] for p in P) / len(P)
        cz = sum(p[2] for p in P) / len(P)
        # orient the normal outward (away from the house centre, or the chimney centre)
        ref = center if not idx[0].startswith("ch") else tf((0.535, 1.2, -0.265))
        if nx * (cx - ref[0]) + ny * (cy - ref[1]) + nz * (cz - ref[2]) < 0:
            nx, ny, nz = -nx, -ny, -nz
        if nx * (0 - cx) + ny * (0 - cy) + nz * (cam - cz) <= 0:
            continue  # faces away from the camera
        lam = 0.72 + 0.32 * max(0.0, nx * light[0] + ny * light[1] + nz * light[2])
        shade = tuple(int(min(255, c * lam)) for c in col)
        bias = 0.3 if idx[0].startswith("q") else 0.0
        polys.append((cz + bias, [proj(p) for p in P], shade))
    for _, pts, shade in sorted(polys, key=lambda q: q[0]):
        d.polygon(pts, fill=shade + (255,))
    return img.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- scenes
def progress_dots(img, n, i, t):
    d = ImageDraw.Draw(img)
    total = n * 34
    x0 = (W - total) / 2
    for k in range(n):
        x = x0 + k * 34
        if k == i:
            p = ease_out(t / 0.4)
            w = 14 + 22 * p
            d.rounded_rectangle([x, 182, x + w, 196], radius=7, fill=INK)
        else:
            d.ellipse([x, 182, x + 14, 196], fill=(200, 200, 205) if k > i else (120, 120, 125))


def draw_hook(img, post, t, dur):
    # 3D house spins in, then settles
    spin = 230 * (1 - ease_out(t / 2.4)) + 25 + 8 * math.sin(t * 1.3)
    sc = 0.55 + 0.45 * ease_back(t / 0.9)
    house = render_house(spin, size=820, scale=sc)
    img.alpha_composite(house, ((W - 820) // 2, 300))
    pill(img, (W - 380) / 2, 1080, f"{post['town'].upper()}, CT", t - 0.3)
    text_block(img, SAFE_X, 1180, post["hook"], font("ExtraBold", 92), INK, W - 2 * SAFE_X, t - 0.5, lh=1.08, center=True)


ICON_WORDS = [
    ("money", ("price", "cost", "tax", "grant", "loan", "$", "budget", "value", "equity", "payment", "afford")),
    ("road", ("commute", "highway", "i-84", "route", "train", "drive", "metro", "transit", "parkway")),
    ("tree", ("outdoor", "park", "trail", "lake", "forest", "river", "nature", "hike", "beach", "foliage")),
    ("shop", ("village", "shop", "dining", "downtown", "restaurant", "store", "food", "market street")),
    ("chart", ("market", "sales", "days on", "inventory", "trend", "data", "comps", "median")),
    ("drop", ("well", "septic", "water", "inspection", "test")),
    ("key", ("buyer", "tip", "offer", "closing", "mortgage", "first-time", "move")),
    ("flag", ("town", "center", "main", "history", "hall", "green", "landmark")),
]


def icon_kind(sc):
    text = (sc.get("label", "") + " " + sc.get("title", "")).lower()
    for kind, words in ICON_WORDS:
        if any(w in text for w in words):
            return kind
    return "pin"


def draw_icon(d, kind, cx, cy, r, p):
    """Line icons, drawn in charcoal; p = 0..1 reveal."""
    lw = max(1, int(r * 0.075))
    c = CHAR
    if kind == "flag":
        d.line([cx - r * .35, cy + r * .55, cx - r * .35, cy - r * .55], fill=c, width=lw)
        d.polygon([(cx - r * .35, cy - r * .55), (cx - r * .35 + r * .75 * p, cy - r * .38), (cx - r * .35, cy - r * .2)], fill=c)
    elif kind == "tree":
        d.polygon([(cx - r * .2, cy - r * .55), (cx - r * .55, cy + r * .15), (cx + r * .15, cy + r * .15)], fill=c)
        d.line([cx - r * .2, cy + r * .15, cx - r * .2, cy + r * .45], fill=c, width=lw)
        for k in range(2):
            y = cy + r * (.3 + .17 * k)
            d.arc([cx + r * .05, y - r * .1, cx + r * .3, y + r * .1], 180, 360, fill=c, width=lw)
            d.arc([cx + r * .3, y - r * .1, cx + r * .55, y + r * .1], 0, 180, fill=c, width=lw)
    elif kind == "shop":
        d.rectangle([cx - r * .5, cy - r * .1, cx + r * .5, cy + r * .5], outline=c, width=lw)
        for k in range(4):
            x0 = cx - r * .55 + k * r * .275
            d.pieslice([x0, cy - r * .5, x0 + r * .275, cy - r * .05], 0, 180, fill=c)
        d.line([cx - r * .55, cy - r * .3, cx + r * .55, cy - r * .3], fill=c, width=lw)
        d.rectangle([cx - r * .12, cy + r * .12, cx + r * .12, cy + r * .5], fill=c)
    elif kind == "road":
        d.polygon([(cx - r * .2, cy - r * .55), (cx + r * .2, cy - r * .55), (cx + r * .55, cy + r * .55), (cx - r * .55, cy + r * .55)], outline=c, width=lw)
        for k in range(3):
            y0 = cy - r * .45 + k * r * .36
            if (k + 1) / 3 <= p + 0.34:
                d.line([cx, y0, cx, y0 + r * .2], fill=c, width=lw)
    elif kind == "money":
        d.text((cx, cy), "$", font=font("Black", int(r * 1.2)), fill=c, anchor="mm")
    elif kind == "chart":
        for k, h in enumerate((.35, .6, .45, .85)):
            x0 = cx - r * .5 + k * r * .27
            d.rectangle([x0, cy + r * .5 - r * h * p, x0 + r * .18, cy + r * .5], fill=c)
    elif kind == "drop":
        d.polygon([(cx, cy - r * .6), (cx - r * .38, cy + r * .1), (cx + r * .38, cy + r * .1)], fill=c)
        d.ellipse([cx - r * .38, cy - r * .2, cx + r * .38, cy + r * .5], fill=c)
    elif kind == "key":
        d.ellipse([cx - r * .55, cy - r * .3, cx - r * .05, cy + r * .2], outline=c, width=lw)
        d.line([cx - r * .05, cy - r * .05, cx + r * .55, cy - r * .05], fill=c, width=lw)
        d.line([cx + r * .35, cy - r * .05, cx + r * .35, cy + r * .2], fill=c, width=lw)
        d.line([cx + r * .5, cy - r * .05, cx + r * .5, cy + r * .15], fill=c, width=lw)
    else:  # map pin
        d.ellipse([cx - r * .4, cy - r * .6, cx + r * .4, cy + r * .2], fill=c)
        d.polygon([(cx - r * .34, cy - r * .05), (cx + r * .34, cy - r * .05), (cx, cy + r * .6)], fill=c)
        d.ellipse([cx - r * .15, cy - r * .35, cx + r * .15, cy - r * .05], fill=GOLD)


def visual_card(img, sc, idx, t):
    """Lower half: a floating gold disc with an icon, the step number beside it."""
    p = ease_back((t - 0.35) / 0.7)
    if p <= 0:
        return
    cx, cy, r = 330, 1190, 230
    bob = 10 * math.sin(t * 2.2)
    rr = r * p
    sh = Image.new("RGBA", (int(r * 2.6), int(r * 0.7)), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([r * 0.4, r * 0.15, r * 2.2, r * 0.5], fill=(0, 0, 0, int(55 * clamp(p))))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)), (int(cx - r * 1.3), int(cy + r * 0.9)))
    disc = Image.new("RGBA", (int(r * 2.2), int(r * 2.2)), (0, 0, 0, 0))
    dd = ImageDraw.Draw(disc)
    c0 = r * 1.1
    for k in range(int(rr), 0, -2):  # radial shading = a soft 3D sphere-ish disc
        f = k / max(rr, 1)
        col = tuple(int(GOLD[i] * (0.82 + 0.18 * (1 - f)) + (255 - GOLD[i]) * 0.25 * (1 - f) ** 2) for i in range(3))
        dd.ellipse([c0 - k, c0 - k - (1 - f) * rr * 0.12, c0 + k, c0 + k - (1 - f) * rr * 0.12], fill=col + (255,))
    draw_icon(dd, icon_kind(sc), c0, c0, rr * 0.95, ease_out((t - 0.6) / 0.8))
    img.alpha_composite(disc, (int(cx - c0), int(cy - c0 + bob)))
    q = ease_out((t - 0.5) / 0.6)
    layer = Image.new("RGBA", (W, 460), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((W - SAFE_X + 20, 230), f"{idx + 1:02d}", font=font("Black", 330),
                               fill=(220, 220, 226, int(255 * q)), anchor="rm")
    img.alpha_composite(layer, (int(80 * (1 - q)), 960))


def draw_scene(img, sc, idx, n, t):
    progress_dots(img, n, idx, t)
    pill(img, SAFE_X, 300, sc["label"].upper(), t - 0.05)
    y = text_block(img, SAFE_X, 420, sc["title"], font("ExtraBold", 104), INK, W - 2 * SAFE_X, t - 0.2, lh=1.05)
    rp = ease_in_out((t - 0.5) / 0.5)
    if rp > 0:
        ImageDraw.Draw(img).rounded_rectangle([SAFE_X, y + 28, SAFE_X + 160 * rp, y + 38], radius=5, fill=GOLD)
    text_block(img, SAFE_X, y + 80, sc["detail"], font("Medium", 54), SUB, W - 2 * SAFE_X - 20, t - 0.6, lh=1.3)
    visual_card(img, sc, idx, t)


def draw_end(img, post, t, logo):
    pill(img, (W - 420) / 2, 360, f"COMMENT {post['cta_keyword']}", t, fill=INK, fg=(255, 255, 255), size=40)
    y = text_block(img, SAFE_X, 520, post.get("cta_line", "Want the numbers on your home?"),
                   font("ExtraBold", 88), INK, W - 2 * SAFE_X, t - 0.2, lh=1.08, center=True)
    p = ease_out((t - 0.6) / 0.5)
    if p > 0:
        card = Image.new("RGBA", (W - 2 * SAFE_X, 420), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle([0, 0, card.width - 1, card.height - 1], radius=40, fill=(255, 255, 255, 255), outline=FAINT, width=3)
        cd.text((card.width / 2, 70), "Jaskaran Singh, REALTOR®", font=font("Bold", 50), fill=INK, anchor="mm")
        cd.text((card.width / 2, 140), "Call/Text (475) 400-0661", font=font("Medium", 42), fill=INK, anchor="mm")
        cd.text((card.width / 2, 200), "@jaskaranrealtor  ·  jaskaranrealtor.com", font=font("Regular", 34), fill=SUB, anchor="mm")
        cd.text((card.width / 2, 255), "English · Hindi · Punjabi · Urdu", font=font("Regular", 32), fill=SUB, anchor="mm")
        lw = 260
        lg = logo.resize((lw, int(logo.height * lw / logo.width)))
        card.alpha_composite(lg, ((card.width - lw) // 2, 300))
        a = card.split()[3].point(lambda v: int(v * p))
        card.putalpha(a)
        shadow = Image.new("RGBA", (card.width + 80, card.height + 80), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle([40, 50, card.width + 40, card.height + 40], radius=40, fill=(0, 0, 0, int(35 * p)))
        img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(24)), (SAFE_X - 40, int(y + 60 - 40 + 40 * (1 - p))))
        img.alpha_composite(card, (SAFE_X, int(y + 60 + 40 * (1 - p))))
    d = ImageDraw.Draw(img)
    d.text((W / 2, 1500), "Brokered by Vylla Home · CT Lic# RES.0820095 · Equal Housing Opportunity",
           font=font("Regular", 26), fill=SUB, anchor="mm")


# ---------------------------------------------------------------- timeline
def words(s):
    return max(1, len(str(s).split()))


def timeline(post, total):
    """Split total seconds across hook, scenes and end card, proportional to spoken words."""
    parts = [("hook", post.get("hook_say", post["hook"]))] + \
            [("scene", s.get("say", s["title"] + " " + s["detail"])) for s in post["scenes"]] + \
            [("end", post.get("cta_say", "Call or text Jaskaran Singh with Vylla Home."))]
    wsum = sum(words(p[1]) for p in parts)
    segs, t = [], 0.0
    for k, (kind, say) in enumerate(parts):
        d = total * words(say) / wsum
        d = max(d, 2.2 if kind != "end" else 3.0)
        segs.append((kind, t, d, k - 1))
        t += d
    scale = total / t
    out, t = [], 0.0
    for kind, _, d, k in segs:
        out.append((kind, t, d * scale, k))
        t += d * scale
    return out


def spoken_script(post):
    return " ".join([post.get("hook_say", post["hook"])] + [s.get("say", "") for s in post["scenes"]] +
                    [post.get("cta_say", "Call or text Jaskaran Singh with Vylla Home.")]).strip()


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def render_motion(post, out_path, voice=None, music=None, music_volume=0.15, wpm=160):
    if not shutil.which("ffmpeg"):
        print("ffmpeg not installed; skipping video")
        return None
    total = duration(voice) + 1.2 if voice else words(spoken_script(post)) / wpm * 60 + 1.5
    total = max(12.0, min(total, 45.0))
    segs = timeline(post, total)
    logo = Image.open(ASSETS / "logos" / "logo_black.png").convert("RGBA")
    frames = int(total * FPS)
    silent = Path(out_path).with_suffix(".silent.mp4")
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                            "-crf", "20", "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
    n = len(post["scenes"])
    OUT = 0.3  # each segment fades and lifts out over its last 0.3 s, then the next one builds in
    for fi in range(frames):
        t = fi / FPS
        img = background()
        for kind, s0, dur, k in segs:
            if not (s0 <= t < s0 + dur):
                continue
            lt = t - s0
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            if kind == "hook":
                draw_hook(layer, post, lt, dur)
            elif kind == "scene":
                draw_scene(layer, post["scenes"][k], k, n, lt)
            else:
                draw_end(layer, post, lt, logo)
            dy = 0
            if kind != "end" and lt > dur - OUT:
                a = clamp((dur - lt) / OUT)
                layer.putalpha(layer.split()[3].point(lambda v, a=a: int(v * a)))
                dy = -int(60 * (1 - a))
            img.alpha_composite(layer, (0, dy) if dy else (0, 0))
        enc.stdin.write(img.convert("RGB").tobytes())
    enc.stdin.close()
    enc.wait()
    _mux(silent, out_path, total, voice, music, music_volume)
    silent.unlink(missing_ok=True)
    return Path(out_path)


def _mux(video, out_path, seconds, voice, music, music_volume):
    seconds = round(seconds, 2)
    fade = f"afade=t=out:st={max(seconds - 1.5, 0)}:d=1.5"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video)]
    if voice and music:
        cmd += ["-i", str(voice), "-stream_loop", "-1", "-i", str(music)]
        audio = (f"[1:a]aresample=44100,adelay=300|300,apad[v];[2:a]aresample=44100,volume={music_volume}[m];"
                 f"[v][m]amix=inputs=2:duration=longest:normalize=0,atrim=0:{seconds},{fade}[a]")
    elif voice:
        cmd += ["-i", str(voice)]
        audio = f"[1:a]aresample=44100,adelay=300|300,apad,atrim=0:{seconds},{fade}[a]"
    elif music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        audio = f"[1:a]aresample=44100,volume={min(music_volume * 3, 0.6)},atrim=0:{seconds},{fade}[a]"
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        audio = f"[1:a]atrim=0:{seconds}[a]"
    cmd += ["-filter_complex", audio, "-map", "0:v", "-map", "[a]", "-t", str(seconds),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ac", "2", str(out_path)]
    subprocess.run(cmd, check=True)
