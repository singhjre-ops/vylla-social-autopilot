"""Draw branded post graphics with Vylla colors, fonts and logo. No AI image cost."""

import io
import shutil
import subprocess

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .config import ASSETS

FONTS = ASSETS / "fonts"


def _font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def _wrap(draw, text, font, max_width):
    words, lines, line = text.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def render(post, theme_label, town, cfg, out_path, size=(1080, 1350), photo_url=None):
    """White, Apple-style graphic: gold label pill, big Inter headline, 3D house or listing photo, clean footer."""
    from .motion import render_house, font as ifont
    w, h = size
    ink, sub, gold = (29, 29, 31), (110, 110, 115), (255, 176, 0)
    img = Image.new("RGBA", size, (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    for y in range(h):  # soft white-to-grey wash
        k = y / h
        draw.line([0, y, w, y], fill=(int(255 - 10 * k), int(255 - 10 * k), int(255 - 8 * k), 255))
    pad = int(w * 0.09)
    vertical = h > w * 1.5
    y = int(h * (0.13 if vertical else 0.1))

    label = f"{theme_label}  ·  {town.upper()}, CT"
    lf = ifont("Bold", int(w * 0.03))
    tw = draw.textlength(label, font=lf)
    ph = int(w * 0.03) + 30
    draw.rounded_rectangle([pad, y, pad + tw + 48, y + ph], radius=ph / 2, fill=gold)
    draw.text((pad + 24, y + ph / 2), label, font=lf, fill=ink, anchor="lm")
    y += ph + int(h * 0.035)

    hf = ifont("ExtraBold", int(w * 0.085))
    for line in _wrap(draw, post.get("hook") or post["headline"], hf, w - 2 * pad):
        draw.text((pad, y), line, font=hf, fill=ink)
        y += int(hf.size * 1.08)
    draw.rounded_rectangle([pad, y + 18, pad + 150, y + 28], radius=5, fill=gold)
    y += 60
    sf = ifont("Medium", int(w * 0.042))
    for line in _wrap(draw, post["subhead"], sf, w - 2 * pad):
        draw.text((pad, y), line, font=sf, fill=sub)
        y += int(sf.size * 1.35)

    foot = h - int(h * (0.2 if vertical else 0.15))
    visual_top, visual_h = y + int(h * 0.03), foot - y - int(h * 0.05)
    if photo_url:
        try:
            photo = Image.open(io.BytesIO(requests.get(photo_url, timeout=30).content)).convert("RGB")
            ph_w = w - 2 * pad
            card = ImageOps.fit(photo, (ph_w, max(visual_h, 200)))
            mask = Image.new("L", card.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, card.width, card.height], radius=36, fill=255)
            img.paste(card, (pad, visual_top), mask)
        except Exception as e:  # a bad photo should not stop the post
            print(f"photo skipped: {e}")
            photo_url = None
    if not photo_url and visual_h > 220:
        side = min(visual_h + 120, w - 2 * pad)
        house = render_house(28, size=side)
        img.alpha_composite(house, ((w - side) // 2, visual_top - 60))

    draw.line([pad, foot, w - pad, foot], fill=(222, 222, 228), width=2)
    agent = cfg["agent"]
    draw.text((pad, foot + int(h * 0.02)), "@jaskaranrealtor", font=ifont("Bold", int(w * 0.03)), fill=ink)
    draw.text((pad, foot + int(h * 0.02) + int(w * 0.045)), f"{agent['website']}  ·  {agent['phone']}",
              font=ifont("Regular", int(w * 0.025)), fill=ink)
    lic = agent.get("license")
    legal = (f"Brokered by {agent['brokerage']}  ·  CT Lic# {lic}  ·  Equal Housing Opportunity" if lic
             else f"Brokered by {agent['brokerage']}  ·  Equal Housing Opportunity")
    draw.text((pad, foot + int(h * 0.02) + int(w * 0.085)), legal, font=ifont("Regular", int(w * 0.02)), fill=sub)
    logo = Image.open(ASSETS / "logos" / "logo_black.png").convert("RGBA")
    lw = int(w * 0.2)
    logo = logo.resize((lw, int(logo.height * lw / logo.width)))
    img.alpha_composite(logo, (w - pad - lw, foot + int(h * 0.025)))
    img.convert("RGB").save(out_path, quality=92)
    return out_path


def make_video(image_path, out_path, seconds=10, voice=None, music=None, music_volume=0.15):
    """Turn a vertical graphic into a slow-zoom video for Reels, TikTok and YouTube Shorts.

    voice: optional WAV voiceover; the video lengthens to fit it (up to 20 s).
    music: optional background track, ducked under the voice and faded out at the end.
    """
    if not shutil.which("ffmpeg"):
        print("ffmpeg not installed; skipping video")
        return None
    if voice:
        from .audio import duration
        seconds = min(max(seconds, duration(voice) + 1.5), 20)
    seconds = round(seconds, 2)
    frames = int(seconds * 30)
    zoom = f"zoompan=z='min(zoom+0.0006,1.08)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(image_path)]
    fade = f"afade=t=out:st={max(seconds - 1.5, 0)}:d=1.5"
    if voice and music:
        cmd += ["-i", str(voice), "-stream_loop", "-1", "-i", str(music)]
        audio = (f"[1:a]aresample=44100,adelay=400|400,apad[v];"
                 f"[2:a]aresample=44100,volume={music_volume}[m];"
                 f"[v][m]amix=inputs=2:duration=longest:normalize=0,atrim=0:{seconds},{fade}[a]")
    elif voice:
        cmd += ["-i", str(voice)]
        audio = f"[1:a]aresample=44100,adelay=400|400,apad,atrim=0:{seconds},{fade}[a]"
    elif music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        audio = f"[1:a]aresample=44100,volume={min(music_volume * 3, 0.6)},atrim=0:{seconds},{fade}[a]"
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        audio = f"[1:a]atrim=0:{seconds}[a]"
    cmd += ["-filter_complex", f"[0:v]{zoom}[vid];{audio}", "-map", "[vid]", "-map", "[a]",
            "-t", str(seconds), "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ac", "2", str(out_path)]
    subprocess.run(cmd, check=True)
    return out_path
