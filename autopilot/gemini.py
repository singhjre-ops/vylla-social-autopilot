"""Write a post with the Gemini API (free tier is enough for one post a day)."""

import json
import os
import time

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
  "hashtags": list of 3-5 hashtags without the # sign, local where possible,
  "hook": max 7 words, the opening line on screen. Lead with the most specific fact or number you were given.
    Never a question like "Thinking of moving?" and never a greeting,
  "hook_say": the spoken hook, one sentence of max 14 words,
  "scenes": exactly 4 objects, each with
      "label": a 1-2 word topic (e.g. "Commute", "Outdoors", "Pricing"),
      "title": 2-4 words, punchy; use a number or proper name when you have one,
      "detail": 8-16 words of concrete, checkable information (names of places, roads, programs),
      "say": one spoken sentence of 10-18 words that covers this scene.
    Each scene must add a new specific fact; no filler scenes,
  "cta_line": max 8 words inviting them to ask for the numbers on a home in this town.
Write "hook_say" and every "say" line in first person, as Jaskaran would say it out loud on camera: short,
natural, contractions, no jargon. He records these lines himself.
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
    resp = _post_with_retries(cfg, key, body)
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    post = json.loads(text)
    missing = {"headline", "subhead", "caption", "short_caption", "hashtags"} - post.keys()
    if missing:
        raise ValueError(f"Gemini response missing keys: {missing}")
    return post


CAROUSEL_RULES = """You write Instagram carousel posts for {name}, {title} with {brokerage}, serving {regions}, Connecticut.
He is a data-driven agent with an engineering background. Voice: plain English, specific, calm, useful. No hype.

Hard rules (fair housing and accuracy):
- Describe properties and places, never people. Never mention or imply race, color, religion, sex,
  disability, familial status, national origin, age, sexual orientation, gender identity, marital status,
  source of income, or veteran status.
- Never say who a home or town is "perfect for" or "ideal for", or call an area safe, exclusive or family-friendly.
- Never rank or rate schools. Never state crime levels. No guarantees about price or appreciation.
- Never invent numbers, prices, percentages, dates or statistics. A number may appear ONLY if it is in the facts
  you were given. Otherwise use step numbers (01, 02...) or no number at all.
- Only name places you are certain exist today and have for years (state parks, landmarks, lakes, long-running
  events, town greens). No restaurants or shops that may have closed.

What works for carousels right now: one idea broken into steps, one idea per slide, every slide readable on its
own, a recap slide people screenshot and send, then one ask.

Return JSON only, with these keys:
  "headline": the cover's first line, max 4 words, sentence case, ends with a period. Never a question or greeting,
  "headline2": the cover's second line (shown in gray), max 4 words, sentence case, finishes the thought,
  "big": optional short figure for the cover (max 7 characters) taken from the facts given, or "",
  "subhead": max 14 words under the cover, ending with "Swipe.",
  "slides": 5 to 7 objects, each {{"title": max 5 words, "big": "" or a step number like "01" or a figure from
      the facts given (max 7 characters), "text": 8-25 words of concrete information}},
  "recap_title": max 4 words, e.g. "Newtown on one slide",
  "recap": 4 to 6 pairs [label max 2 short words, or the step number like "01"; value max 6 words],
  "cta_title": max 5 words,
  "cta_text": max 18 words, first person, saying what Jaskaran will send personally. Offer only: homes for sale
     right now, recent sales numbers for their street, or a price check on their home. Never promise a guide,
     PDF, checklist, ebook or "resources",
  "caption": 80-150 words in first person ("I", never "we" or "our"), like a local agent texting a friend.
     Line one is a hook of max 120 characters that names something specific. Short paragraphs, mixed sentence
     lengths, contractions. Exactly one ask at the end: comment the keyword you were given, and say what you'll
     send (same offer as cta_text). Include "<Town> CT" once as a phrase people search.
     Never use: navigate, navigating, journey, nestled, vibrant, boasts, delve, seamless, elevate, unlock,
     discover, explore, hidden gem, look no further, dream home, informed decisions, in today's market,
  "short_caption": max 200 characters for TikTok,
  "hashtags": list of 3-5 specific local hashtags without the # sign,
  "alt": one sentence describing the cover for screen readers.
Do not include phone numbers, disclaimers or the brokerage line; they are added later."""


def generate_carousel(cfg, brief):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set. Get a free key at https://aistudio.google.com/apikey")
    agent = cfg["agent"]
    system = CAROUSEL_RULES.format(name=agent["name"], title=agent["title"], brokerage=agent["brokerage"],
                                   regions=", ".join(cfg["regions"]))
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": brief}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.8},
    }
    resp = _post_with_retries(cfg, key, body)
    post = json.loads(resp.json()["candidates"][0]["content"]["parts"][0]["text"])
    missing = {"headline", "slides", "caption", "short_caption", "hashtags"} - post.keys()
    if missing or not isinstance(post.get("slides"), list) or len(post["slides"]) < 3:
        raise ValueError(f"Gemini carousel response incomplete: missing {missing}")
    post.setdefault("subhead", "")
    return post


RETRY_STATUS = {429, 500, 502, 503, 504}
FALLBACK_MODELS = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest", "gemini-2.5-flash-lite"]


def _post_with_retries(cfg, key, body):
    """Try the configured model, then fallbacks. Retry overloads (503) and rate limits (429) with backoff."""
    models = [cfg["gemini"]["model"]] + [m for m in FALLBACK_MODELS if m != cfg["gemini"]["model"]]
    last = None
    for model in models:
        for wait in (0, 10, 30, 60):
            if wait:
                time.sleep(wait)
            try:
                resp = requests.post(
                    API.format(model=model),
                    headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                    json=body,
                    timeout=90,
                )
            except requests.RequestException as e:
                last = f"{model}: {e}"
                continue
            if resp.ok:
                return resp
            last = f"{model}: HTTP {resp.status_code} {resp.text[:300]}"
            print(f"Gemini {last}")
            if resp.status_code == 404:
                break                      # model name not available; try the next one
            if resp.status_code not in RETRY_STATUS:
                raise RuntimeError(f"Gemini request failed: {last}")
    raise RuntimeError(f"Gemini unavailable after retries and fallbacks. Last error: {last}")
