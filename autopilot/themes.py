"""Post themes. Each theme gives Gemini a brief and tells the renderer which label to show."""

THEMES = {
    "market_update": {
        "label": "MARKET DATA",
        "brief": (
            "Write a market data post for {town}, CT using ONLY these Redfin figures: {stats}. "
            "Lead with the single most surprising number. Say 'typical sale price', 'days to sell' and "
            "'percent of asking price', never jargon like median, DOM or YoY. Explain what each number means "
            "for someone selling and for someone buying, in plain language. Do not add any other numbers, "
            "estimates, predictions or comparisons to other places."
        ),
        "needs": "stats",
        "carousel": ("Make it a numbers breakdown: cover hooks with the most surprising figure; then one slide per "
                     "figure (big = the figure exactly as given, e.g. $679,652 or 56 days), each with what it means; "
                     "then 'If you're selling' and 'If you're buying' slides. Every number must come from the figures."),
        "keyword": "VALUE",
    },
    "market_compare": {
        "label": "MARKET DATA",
        "brief": (
            "Write a post comparing these Greater Danbury towns using ONLY these Redfin figures: {stats}. "
            "Pick ONE angle, for example where homes sell fastest, where prices moved most vs. last year, or "
            "where buyers paid over asking. Say 'typical sale price', 'days to sell' and 'percent of asking price', "
            "never jargon. Describe markets and numbers only, never the people who live in a town. "
            "Do not add any other numbers, estimates or predictions."
        ),
        "needs": "stats",
        "carousel": ("Make it a ranked list for that one angle: cover states the angle; then one slide per town in "
                     "ranked order (big = the figure exactly as given), with one line on what it means; then a recap "
                     "slide listing each town and its figure. Every number must come from the figures."),
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
