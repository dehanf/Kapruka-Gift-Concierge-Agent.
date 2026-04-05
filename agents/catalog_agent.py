# agents/catalog_agent.py

from memory.lt_memory import search_catalog
from agents import critic_agent
from utils.config import CLAUDE_MODEL, CLAUDE_MAX_TOKENS_RESPOND, CLAUDE_MAX_TOKENS_CRITIQUE, MAX_REFLECTION_ROUNDS, CATALOG_SEARCH_TOP_K, CATALOG_MAX_PRODUCTS
from utils.prompts import CATALOG_SYSTEM_PROMPT, REVISE_SYSTEM_PROMPT
from infrastructure.llm.client import chat


def _generate(user_content: str) -> str:
    return chat(
        system=CATALOG_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
        max_tokens=CLAUDE_MAX_TOKENS_RESPOND,
        model=CLAUDE_MODEL,
    )


def _revise(recommendation: str, issues: list, suggestion: str) -> str:
    content = (
        f"Original recommendation:\n{recommendation}\n\n"
        f"Issues found:\n" + "\n".join(f"- {i}" for i in issues) +
        f"\n\nSuggested fix:\n{suggestion or 'Address the issues above.'}"
    )
    return chat(
        system=REVISE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
        max_tokens=CLAUDE_MAX_TOKENS_RESPOND,
        model=CLAUDE_MODEL,
    )


def run(customer_id: str, recipient: str, search_query: str,old_profile: dict, new_profile: dict) -> str:

    # 1. Use old profile directly - no get_profile() call needed
    profile = old_profile
    allergies = [a.lower() for a in profile.get("allergies",[])]

    # 2. Search the catalog
    products = search_catalog(search_query, top_k=CATALOG_SEARCH_TOP_K)

    if not products:
        return "Sorry ! Unfortunately i couldn't find anything matching right now. Could you try describing the gift differently?"

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

    # 4. Keep top N after filtering
    products = products[:CATALOG_MAX_PRODUCTS]

    # 5. Build context using old profile 
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

    # 7. Merge old profile and new profile
    merged_profile = {
    "allergies": list(set(
        [a.lower() for a in old_profile.get("allergies", [])] +
        [a.lower() for a in new_profile.get("allergies", [])]
    )),
    "preferences": list(set(
        old_profile.get("preferences", []) +
        new_profile.get("preferences", [])
    )),
    "location": new_profile.get("location") or old_profile.get("location", "unknown")

    }
    
    # 8. Skip critic if no constraints at all
    skip_critic = not merged_profile.get("allergies") and not merged_profile.get("preferences")
    if skip_critic:
        print("[Critic] Skipped — no constraints.")
        return recommendation

    # 9. Reflection loop
    for round_num in range(1, MAX_REFLECTION_ROUNDS + 1):
        critique = critic_agent.critique(
            recommendation=recommendation,
            search_query=search_query,
            profile=merged_profile,
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
