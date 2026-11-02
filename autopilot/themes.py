"""Post themes. Each theme gives Gemini a brief and tells the renderer which label to show."""

THEMES = {
    "market_update": {
        "label": "MARKET UPDATE",
        "brief": (
            "Write a monthly market update for {town}, CT using ONLY these Smart MLS figures: {stats}. "
            "Explain what the numbers mean for buyers and sellers in plain language."
        ),
        "needs": "stats",
        "carousel": "Make it a market breakdown: one figure per slide with what it means, then what it means if you sell.",
        "keyword": "VALUE",
    },
    "town_spotlight": {
        "label": "TOWN SPOTLIGHT",
        "brief": (
            "Write a town spotlight on {town}, CT: well-known landmarks, parks, lakes, trails, downtown, "
            "commuter rail or highway access, and seasonal events. It is {month}. "
            "Describe places and amenities, never the people who live there."
        ),
        "carousel": ("Make it a '{town} starter pack': 5 or 6 numbered slides (big = 01, 02...), each one specific, "
                     "long-standing place or tradition locals would tell a newcomer about, with one line on why."),
        "keyword": "MOVE",
    },
    "listing_spotlight": {
        "label": "JUST LISTED",
        "brief": (
            "Write a listing post for {address}, {town}, CT. Facts: {listing}. "
            "Describe the property's features only. Use only the facts given."
        ),
        "needs": "listing",
    },
    "seller_tip": {
        "label": "SELLER TIP",
        "brief": (
            "Write one practical, specific tip for homeowners thinking about selling in {town}, CT this {month}. "
            "Topics to rotate: pricing strategy, pre-listing repairs, staging, timing, inspections, CT closing steps."
        ),
        "carousel": "Make it a step-by-step seller playbook on ONE topic: numbered steps (big = 01, 02...), each a concrete action.",
        "keyword": "VALUE",
    },
    "buyer_tip": {
        "label": "BUYER TIP",
        "brief": (
            "Write one practical, specific tip for home buyers looking in {town}, CT this {month}. "
            "Topics to rotate: pre-approval, CHFA first-time buyer programs, offers, inspections, "
            "CT property taxes and mill rates, closing costs."
        ),
        "carousel": "Make it a step-by-step buyer explainer on ONE topic: numbered steps (big = 01, 02...), or a checklist.",
        "keyword": "BUY",
    },
    "community_life": {
        "label": "LOCAL LIFE",
        "brief": (
            "Write a friendly local-life post about things to do in or near {town}, CT this {month}: "
            "farms, trails, restaurants by type, seasonal events. Keep it general enough to stay true."
        ),
        "carousel": "Make it a numbered local guide (big = 01, 02...) of long-standing places and seasonal traditions.",
        "keyword": "MOVE",
    },
}
