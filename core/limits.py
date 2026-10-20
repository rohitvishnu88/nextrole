"""Monthly allowances, the overall ceiling, and prices used to measure spend."""

ACTION_LIMITS = {
    "job_search": 4,
    "tailor": 12,
    "analyse": 15,
    "section_draft": 20,
    "resume_parse": 3,
    "search_brief": 3,
}

# Held against the ceiling while an action is in flight; worst-case per action.
ACTION_ESTIMATES_USD = {
    "job_search": 0.60,
    "tailor": 0.30,
    "analyse": 0.10,
    "section_draft": 0.03,
    "resume_parse": 0.05,
    "search_brief": 0.01,
    "cli": 0.30,
}

MONTHLY_BUDGET_USD = 50.0

# USD per million tokens. Checked against Anthropic's published prices on 2026-10-20.
# Cache writes bill at 1.25x input, cache reads at 0.1x input.
PRICES = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}
CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.10

# Tavily pay-as-you-go rate, used even on the free tier so the ceiling stays conservative.
TAVILY_CREDIT_USD = 0.008


def price_for(model: str) -> dict:
    """Match dated model ids (claude-haiku-4-5-20251001) to their family; unknown models
    are priced as the most expensive known one rather than as free."""
    for family, price in PRICES.items():
        if model.startswith(family):
            return price
    return max(PRICES.values(), key=lambda p: p["output"])
