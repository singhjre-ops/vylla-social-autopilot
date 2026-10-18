"""Block fair-housing red flags and add the required brokerage disclosure.

This is a safety net, not legal review. It catches common problem phrases; you still approve posts.
"""

import re

# Phrases HUD and NAR guidance flag as steering or discriminatory in housing ads.
BLOCKED = [
    r"perfect for (a )?(young )?(famil|couple|single|retiree|professional|student|kids|children)",
    r"ideal for (a )?(young )?(famil|couple|single|retiree|professional|student|kids|children)",
    r"great for (famil|couple|single|retiree|kids|children)",
    r"family[- ]friendly", r"\bfamily neighborhood\b", r"\bno (kids|children)\b", r"\badults? only\b",
    r"\bsafe (neighborhood|area|community|town|street)\b", r"\bsafest\b", r"\blow crime\b", r"\bcrime[- ]free\b",
    r"\bexclusive (neighborhood|community|area)\b", r"\bprivate community\b",
    r"\b(best|top[- ]rated|good|great|excellent) schools?\b", r"\bschool rankings?\b",
    r"\b(christian|jewish|muslim|catholic|hindu|sikh)\b",
    r"\bbachelor pad\b", r"\bmother[- ]in[- ]law\b", r"\bman cave\b", r"\bempty[- ]nesters?\b",
    r"\bmature (couple|individual|person)s?\b", r"\bsenior(s| citizens?)\b", r"\bretirees?\b",
    r"\bable[- ]bodied\b", r"\bhandicap(ped)?\b",
    r"\bethnic\b", r"\bhomogeneous\b", r"\bdesirable (neighborhood|area)\b",
    r"\bno section 8\b", r"\bsection 8\b", r"\bEnglish only\b",
    r"\bguarantee[ds]?\b", r"\bwill appreciate\b", r"\bcan'?t lose\b",
]
PHONE = re.compile(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")


def check(post, cfg):
    """Return a list of problems. An empty list means the post passed."""
    problems = []
    text = " ".join([post["headline"], post["subhead"], post["caption"], post["short_caption"],
                     " ".join(post["hashtags"])])
    for pattern in BLOCKED:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            problems.append(f'fair housing: "{m.group(0)}"')
    for m in PHONE.finditer(text):
        problems.append(f'unexpected phone number "{m.group(0)}" (the disclosure adds yours)')
    if len(post["short_caption"]) > 220:
        problems.append("short_caption over 220 characters")
    return problems


def finalize(post, cfg):
    """Add hashtags and the brokerage disclosure. Returns captions keyed by format."""
    tags = " ".join("#" + t.lstrip("#").replace(" ", "") for t in post["hashtags"])
    disclosure = cfg["disclosure"]
    if cfg["agent"]["brokerage"] not in disclosure:
        raise ValueError("config disclosure must include the brokerage name")
    long_caption = f"{post['caption'].strip()}\n\n{tags}\n\n{disclosure}"
    short = f"{post['short_caption'].strip()}\n{cfg['agent']['brokerage']} | {cfg['agent']['phone']}"
    return {"long": long_caption, "short": short, "gmb": f"{post['caption'].strip()}\n\n{disclosure}"}
