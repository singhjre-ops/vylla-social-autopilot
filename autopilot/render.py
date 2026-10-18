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
    b = cfg["brand"]
    w, h = size
    img = Image.new("RGB", size, b["charcoal"])
    draw = ImageDraw.Draw(img)
    pad = int(w * 0.08)

    # Listing photo on the top half when one is available.
    vertical = h > w * 1.5  # TikTok / Shorts: app buttons cover the bottom ~20%
    text_top = int(h * (0.3 if vertical else 0.22))
    if photo_url:
        try:
            photo = Image.open(io.BytesIO(requests.get(photo_url, timeout=30).content)).convert("RGB")
            photo_h = int(h * 0.5)
            img.paste(ImageOps.fit(photo, (w, photo_h)), (0, 0))
            text_top = photo_h + int(h * 0.05)
        except Exception as e:  # a bad photo should not stop the post
            print(f"photo skipped: {e}")

    # Theme label with New Day accent bar.
    label_font = _font("Roboto-Bold.ttf", int(w * 0.03))
    label_y = text_top - int(h * 0.07)
    draw.rectangle([pad, label_y, pad + int(w * 0.06), label_y + 8], fill=b["new_day"])
    draw.text((pad, label_y + 24), f"{theme_label}  ·  {town.upper()}, CT", font=label_font, fill=b["new_day"])

    # Headline, then subhead.
    max_w = w - 2 * pad
    head_size = int(w * (0.075 if not photo_url else 0.06))
    head_font = _font("LibreBaskerville-Regular.ttf", head_size)
    y = label_y + 90
    for line in _wrap(draw, post["headline"], head_font, max_w):
        draw.text((pad, y), line, font=head_font, fill=b["cream"])
        y += int(head_size * 1.3)
    y += int(h * 0.025)
    sub_font = _font("Roboto-Light.ttf", int(w * 0.038))
    for line in _wrap(draw, post["subhead"], sub_font, max_w):
        draw.text((pad, y), line, font=sub_font, fill=b["cream"])
        y += int(w * 0.052)

    # Footer: agent, brokerage, phone, logo (CT requires brokerage name on ads).
    agent = cfg["agent"]
    foot_y = h - int(h * (0.24 if vertical else 0.12))
    draw.line([pad, foot_y - 30, w - pad, foot_y - 30], fill=b["grey"], width=2)
    name_font = _font("Roboto-Bold.ttf", int(w * 0.032))
    info_font = _font("Roboto-Light.ttf", int(w * 0.026))
    draw.text((pad, foot_y), f"{agent['name']}, {agent['title']}", font=name_font, fill=b["cream"])
    draw.text((pad, foot_y + int(w * 0.045)), f"{agent['website']}  ·  {agent['phone']}", font=info_font,
              fill=b["cream"])
    small_font = _font("Roboto-Light.ttf", int(w * 0.021))
    lic = agent.get("license")
    legal = f"Brokered by {agent['brokerage']}  ·  CT Lic# {lic}  ·  Equal Housing Opportunity" if lic \
        else "Equal Housing Opportunity"
    draw.text((pad, foot_y + int(w * 0.085)), legal, font=small_font, fill=b["cream"])
    logo = Image.open(ASSETS / "logos" / "logo_white.png")
    logo_w = int(w * 0.26)
    logo = logo.resize((logo_w, int(logo.height * logo_w / logo.width)))
    img.paste(logo, (w - pad - logo_w, foot_y + 5), logo)

    img.save(out_path, quality=92)
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
