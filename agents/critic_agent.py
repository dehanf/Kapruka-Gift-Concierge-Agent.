# agents/critic_agent.py

import json
import anthropic

client = anthropic.Anthropic()

CRITIC_SYSTEM_PROMPT = """You are a quality reviewer for a gift recommendation concierge.

You will be given:
- The recipient's profile (allergies, preferences, location)
- The search query the customer made
- The product list that was available
- The recommendation text that was generated

Your job is to critique the recommendation strictly. Check for:
1. SAFETY — Does it recommend anything containing the recipient's allergens?
2. RELEVANCE — Does it actually match what the customer searched for?
3. ACCURACY — Does it correctly state prices and availability from the product list?
4. QUALITY — Is it helpful, specific, and natural? (Not vague or generic)

Respond ONLY with a JSON object in this exact format (no other text, no markdown):
{
  "approved": true,
  "issues": [],
  "suggestion": null
}

Or if there are problems:
{
  "approved": false,
  "issues": ["Recommends a product with nuts despite nut allergy", "Price stated incorrectly"],
  "suggestion": "Remove the walnut cake suggestion. Correct the price of the chocolate cake to Rs. 2500."
}

Be strict. If anything is wrong, set approved to false."""


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
        model="claude-opus-4-5",
        max_tokens=300,
        system=CRITIC_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": context}]
    )

    raw = response.content[0].text.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"approved": True, "issues": [], "suggestion": None}
