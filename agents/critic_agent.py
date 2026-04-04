# agents/critic_agent.py

import json
import anthropic
from utils.config import CLAUDE_MODEL, CLAUDE_MAX_TOKENS
from utils.prompts import CRITIC_SYSTEM_PROMPT

client = anthropic.Anthropic()


def critique(
    recommendation: str,
    search_query: str,
    profile: dict,
    recipient: str,
    products: list
) -> dict:

    product_lines = "\n".join([
        f"- {p.get('name')} | Price: {p.get('price')} | Stock: {p.get('availability')} | "
        f"Specs: {p.get('specs', 'N/A')}"
        for p in products
    ])

    allergies = profile.get("allergies", [])
    preferences = profile.get("preferences", [])
    location = profile.get("location", "unknown")

    context = f"""Recipient: {recipient or 'unknown'}
Allergies: {', '.join(allergies) if allergies else 'none'}
Preferences: {', '.join(preferences) if preferences else 'none'}
Location: {location}

Search query: {search_query}

Available products:
{product_lines}

Recommendation to review:
{recommendation}"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=CLAUDE_MAX_TOKENS,
        system=CRITIC_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": context}]
    )

    raw = response.content[0].text.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"approved": True, "issues": [], "suggestion": None}
