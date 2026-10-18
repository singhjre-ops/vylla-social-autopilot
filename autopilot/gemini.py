"""Write a post with the Gemini API (free tier is enough for one post a day)."""

import json
import os

import requests

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

RULES = """You write social media posts for {name}, {title} with {brokerage}, serving {regions}, Connecticut.
Voice: warm, local, knowledgeable, plain English. No hype, no clickbait.

Hard rules (fair housing and accuracy):
- Describe properties and places, never people. Never mention or imply race, color, religion, sex,
  disability, familial status, national origin, age, sexual orientation, gender identity, marital status,
  source of income, or veteran status.
- Never say who a home or town is "perfect for" or "ideal for", or call an area safe, exclusive or family-friendly.
- Never rank or rate schools. Never state crime levels.
- Never invent numbers, prices, statistics, dates or events. Use only facts given to you; otherwise speak generally.
- No guarantees about price, appreciation or investment returns.

Return JSON only, with these keys:
  "headline": max 8 words for the graphic,
  "subhead": max 14 words for the graphic,
  "caption": 80-150 words for Facebook, Instagram and Google Business Profile, ending with a call to action,
  "short_caption": max 220 characters for X and TikTok,
  "hashtags": list of 5-8 hashtags without the # sign, local where possible.
Do not include phone numbers, disclaimers or the brokerage line; they are added later."""


def generate(cfg, brief):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set. Get a free key at https://aistudio.google.com/apikey")
    agent = cfg["agent"]
    system = RULES.format(
        name=agent["name"], title=agent["title"], brokerage=agent["brokerage"],
        regions=", ".join(cfg["regions"]),
    )
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": brief}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.9},
    }
    resp = requests.post(
        API.format(model=cfg["gemini"]["model"]),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json=body,
        timeout=60,
    )
    resp.raise_for_status()
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    post = json.loads(text)
    missing = {"headline", "subhead", "caption", "short_caption", "hashtags"} - post.keys()
    if missing:
        raise ValueError(f"Gemini response missing keys: {missing}")
    return post
