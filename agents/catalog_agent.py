# agents/catalog_agent.py

import anthropic
from memory.lt_memory import search_catalog
from memory.semantic_memory import get_profile
from agents import critic_agent

client = anthropic.Anthropic()

MAX_REFLECTION_ROUNDS = 2

CATALOG_SYSTEM_PROMPT = """You are a warm and helpful gift concierge for Kapruka, a Sri Lankan gifting platform.

You will be given:
- Who the gift is for and any known preferences or allergies
- A list of matching products from the catalog

Write a short, friendly recommendation (3-5 sentences) that:
- Suggests the top 1-3 products by name and price
- Mentions why each suits the recipient (occasion, preferences)
- Warns if stock is limited or a product is unavailable
- Stays concise — no bullet walls, just natural conversation

Respond in plain text only. No markdown."""

REVISE_SYSTEM_PROMPT = """You are a gift concierge revising a recommendation based on a critic's feedback.

You will be given the original recommendation and specific issues found.
Fix only what the critic flagged. Keep everything else the same.
Respond in plain text only. No markdown."""


def _generate(user_content: str) -> str:
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=300,
        system=CATALOG_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}]
    )
    return response.content[0].text.strip()


def _revise(recommendation: str, issues: list, suggestion: str) -> str:
    content = (
        f"Original recommendation:\n{recommendation}\n\n"
        f"Issues found:\n" + "\n".join(f"- {i}" for i in issues) +
        f"\n\nSuggested fix:\n{suggestion or 'Address the issues above.'}"
    )
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=300,
        system=REVISE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}]
    )
    return response.content[0].text.strip()


def run(customer_id: str, recipient: str, search_query: str) -> str:

    # 1. Get recipient profile for allergy/preference filtering
    profile = get_profile(customer_id, recipient) if recipient else {}
    allergies = [a.lower() for a in profile.get("allergies", [])]

    # 2. Search the catalog
    products = search_catalog(search_query, top_k=8)

    if not products:
        return "I searched our catalog but couldn't find anything matching that right now. Could you try describing the gift differently?"

    # 3. Filter out products that contain allergens
    if allergies:
        def is_safe(product: dict) -> bool:
            searchable = " ".join([
                product.get("name", ""),
                product.get("description", ""),
                product.get("specs", "")
            ]).lower()
            return not any(allergen in searchable for allergen in allergies)

        safe_products = [p for p in products if is_safe(p)]

        if not safe_products:
            return (
                f"I found some results but all of them may contain {', '.join(allergies)}, "
                f"which {recipient or 'the recipient'} is allergic to. "
                "Could you try a different type of gift?"
            )
        products = safe_products

    # 4. Keep top 5 after filtering
    products = products[:5]

    # 5. Build context string for Claude
    profile_summary = ""
    if profile:
        profile_summary = (
            f"Recipient: {recipient}\n"
            f"Allergies: {', '.join(allergies) if allergies else 'none'}\n"
            f"Preferences: {', '.join(profile.get('preferences', [])) or 'none'}\n"
            f"Location: {profile.get('location', 'unknown')}\n"
        )

    product_lines = [
        f"- {p.get('name', 'Unknown')} | Price: {p.get('price', 'N/A')} "
        f"| Category: {p.get('category', 'N/A')} | Stock: {p.get('availability', 'Unknown')}"
        for p in products
    ]

    user_content = (
        f"{profile_summary}\n"
        f"Search: {search_query}\n\n"
        f"Matching products:\n" + "\n".join(product_lines)
    )

    # 6. Generate initial recommendation
    recommendation = _generate(user_content)
    print(f"\n[Catalog] Draft recommendation generated.")

    # 7. Reflection loop
    for round_num in range(1, MAX_REFLECTION_ROUNDS + 1):
        critique = critic_agent.critique(
            recommendation=recommendation,
            search_query=search_query,
            profile=profile,
            recipient=recipient or "",
            products=products
        )

        if critique.get("approved"):
            print(f"[Critic] Approved on round {round_num}.")
            break

        issues = critique.get("issues", [])
        suggestion = critique.get("suggestion")
        print(f"[Critic] Round {round_num} — issues found: {issues}")

        recommendation = _revise(recommendation, issues, suggestion)

    return recommendation
