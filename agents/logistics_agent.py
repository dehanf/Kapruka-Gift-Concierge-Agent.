# agents/logistics_agent.py

import anthropic
from utils.config import CLAUDE_MODEL, CLAUDE_MAX_TOKENS
from utils.prompts import LOGISTICS_SYSTEM_PROMPT

client = anthropic.Anthropic()

# Kapruka delivery coverage for Sri Lankan districts
# tier 1 = next-day, tier 2 = 2-3 days, tier 3 = 3-5 days
DISTRICT_COVERAGE = {
    # Western Province
    "colombo":       {"covered": True,  "tier": 1, "label": "Colombo"},
    "gampaha":       {"covered": True,  "tier": 1, "label": "Gampaha"},
    "kalutara":      {"covered": True,  "tier": 1, "label": "Kalutara"},
    # Central Province
    "kandy":         {"covered": True,  "tier": 2, "label": "Kandy"},
    "matale":        {"covered": True,  "tier": 2, "label": "Matale"},
    "nuwara eliya":  {"covered": True,  "tier": 2, "label": "Nuwara Eliya"},
    # Southern Province
    "galle":         {"covered": True,  "tier": 2, "label": "Galle"},
    "matara":        {"covered": True,  "tier": 2, "label": "Matara"},
    "hambantota":    {"covered": True,  "tier": 3, "label": "Hambantota"},
    # Northern Province
    "jaffna":        {"covered": True,  "tier": 3, "label": "Jaffna"},
    "kilinochchi":   {"covered": False, "tier": None, "label": "Kilinochchi"},
    "mannar":        {"covered": False, "tier": None, "label": "Mannar"},
    "vavuniya":      {"covered": True,  "tier": 3, "label": "Vavuniya"},
    "mullaitivu":    {"covered": False, "tier": None, "label": "Mullaitivu"},
    # Eastern Province
    "trincomalee":   {"covered": True,  "tier": 3, "label": "Trincomalee"},
    "batticaloa":    {"covered": True,  "tier": 3, "label": "Batticaloa"},
    "ampara":        {"covered": True,  "tier": 3, "label": "Ampara"},
    # North Western Province
    "kurunegala":    {"covered": True,  "tier": 2, "label": "Kurunegala"},
    "puttalam":      {"covered": True,  "tier": 2, "label": "Puttalam"},
    # North Central Province
    "anuradhapura":  {"covered": True,  "tier": 2, "label": "Anuradhapura"},
    "polonnaruwa":   {"covered": True,  "tier": 3, "label": "Polonnaruwa"},
    # Uva Province
    "badulla":       {"covered": True,  "tier": 3, "label": "Badulla"},
    "monaragala":    {"covered": True,  "tier": 3, "label": "Monaragala"},
    # Sabaragamuwa Province
    "ratnapura":     {"covered": True,  "tier": 2, "label": "Ratnapura"},
    "kegalle":       {"covered": True,  "tier": 2, "label": "Kegalle"},
}

TIER_DESCRIPTION = {
    1: "next-day delivery",
    2: "2–3 day delivery",
    3: "3–5 day delivery",
}


def _lookup(location: str) -> dict:
    """Return coverage info for a location string, or None if not found."""
    key = location.strip().lower()
    return DISTRICT_COVERAGE.get(key)


def run(location: str | None, deadline: str | None = None, tracking_code: str | None = None) -> str:
    # Tracking flow — Playwright integration goes here
    if tracking_code:
        return f"[Tracking stub] Order {tracking_code} — Playwright lookup not yet implemented."

    if not location:
        return (
            "I'd be happy to check delivery for you! "
            "Could you let me know which district or city in Sri Lanka you'd like the gift delivered to?"
        )

    coverage = _lookup(location)

    if coverage is None:
        # Unknown location — let llm handle gracefully
        context = (
            f"Location requested: {location}\n"
            f"Status: not found in our district database\n"
            f"Deadline: {deadline or 'not specified'}"
        )
    elif coverage["covered"]:
        tier = coverage["tier"]
        context = (
            f"Location requested: {coverage['label']}\n"
            f"Status: covered\n"
            f"Delivery speed: {TIER_DESCRIPTION[tier]}\n"
            f"Deadline: {deadline or 'not specified'}"
        )
    else:
        context = (
            f"Location requested: {coverage['label']}\n"
            f"Status: not currently covered by Kapruka delivery\n"
            f"Deadline: {deadline or 'not specified'}"
        )

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=CLAUDE_MAX_TOKENS,
        system=LOGISTICS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": context}]
    )

    return response.content[0].text.strip()
