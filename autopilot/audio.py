"""Voiceover (Gemini text-to-speech) and background music for the vertical videos.

Every step is optional: if the voiceover fails or no music is in assets/music/,
the video still renders, with whatever audio is available (or silence).
"""

import base64
import os
import subprocess
import time
from pathlib import Path

import requests

from .config import ASSETS

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TTS_MODELS = ["gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts"]
MUSIC_DIR = ASSETS / "music"
MUSIC_EXT = {".mp3", ".m4a", ".wav", ".aac", ".ogg"}


def voiceover(cfg, script, out_wav):
    """Write a WAV voiceover for `script`. Returns the path, or None if it could not be made."""
    vcfg = cfg.get("voiceover", {})
    key = os.environ.get("GEMINI_API_KEY")
    if not vcfg.get("enabled", True) or not key or not script:
        return None
    style = vcfg.get("style", "Say in a warm, confident, conversational tone, at a natural pace:")
    body = {
        "contents": [{"parts": [{"text": f"{style} {script}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": vcfg.get("voice", "Charon")}}},
        },
    }
    models = [vcfg["model"]] if vcfg.get("model") else []
    models += [m for m in TTS_MODELS if m not in models]
    for model in models:
        for wait in (0, 10, 30):
            if wait:
                time.sleep(wait)
            try:
                r = requests.post(API.format(model=model), json=body, timeout=120,
                                  headers={"x-goog-api-key": key, "Content-Type": "application/json"})
            except requests.RequestException as e:
                print(f"voiceover {model}: {e}")
                continue
            if r.ok:
                try:
                    part = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
                    pcm = base64.b64decode(part["data"])
                except (KeyError, IndexError, ValueError) as e:
                    print(f"voiceover {model}: unexpected response ({e})")
                    break
                raw = Path(out_wav).with_suffix(".pcm")
                raw.write_bytes(pcm)
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", "24000", "-ac", "1",
                                "-i", str(raw), str(out_wav)], check=True)
                raw.unlink()
                return Path(out_wav)
            print(f"voiceover {model}: HTTP {r.status_code} {r.text[:200]}")
            if r.status_code not in (429, 500, 502, 503, 504):
                break  # wrong model name or not allowed on this key; try the next model
    print("voiceover unavailable; video will use music only")
    return None


def pick_music(index):
    """Rotate through the tracks in assets/music/ (sorted by name)."""
    if not MUSIC_DIR.exists():
        return None
    tracks = sorted(p for p in MUSIC_DIR.iterdir() if p.suffix.lower() in MUSIC_EXT)
    return tracks[index % len(tracks)] if tracks else None


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def music_credit(track):
    """Attribution text for a track: a .txt file with the same name next to it (e.g. song.mp3 + song.txt).

    Creative Commons BY tracks must credit the artist on every post that uses them.
    """
    if not track:
        return None
    txt = Path(track).with_suffix(".txt")
    return txt.read_text(encoding="utf-8").strip() if txt.exists() else None
