# agents/catalog_agent.py

from memory.lt_memory import search_catalog
from agents import critic_agent
from utils.config import CLAUDE_MODEL, CLAUDE_MAX_TOKENS_RESPOND, CLAUDE_MAX_TOKENS_CRITIQUE, MAX_REFLECTION_ROUNDS, CATALOG_SEARCH_TOP_K, CATALOG_MAX_PRODUCTS
from utils.prompts import CATALOG_SYSTEM_PROMPT, REVISE_SYSTEM_PROMPT
from infrastructure.llm.client import chat, chat_stream


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

def _generate_stream(user_content: str):
    """Streaming version of _generate() — yields chunks as LLM generates."""
    yield from chat_stream(
        system=CATALOG_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
        max_tokens=CLAUDE_MAX_TOKENS_RESPOND,
        model=CLAUDE_MODEL,
    )


def run_stream(customer_id: str, recipient: str, search_query: str, old_profile: dict, new_profile: dict,query_vector : list = None):

    profile = old_profile
    allergies = [a.lower() for a in profile.get("allergies", [])]

    # Search catalog
    products = search_catalog(search_query, top_k=CATALOG_SEARCH_TOP_K,query_vector=query_vector)
    if not products:
        yield "Sorry! I couldn't find anything matching right now. Could you try describing the gift differently?"
        return

    # Filter allergens
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
            yield (
                f"I found some results but all of them may contain {', '.join(allergies)}, "
                f"which {recipient or 'the recipient'} is allergic to. "
                "Could you try a different type of gift?"
            )
            return
        products = safe_products

    products = products[:CATALOG_MAX_PRODUCTS]

    # Build context
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

    # 1. Stream draft — collect full text while yielding chunks
    draft_chunks = []
    for chunk in _generate_stream(user_content):
        draft_chunks.append(chunk)
        yield chunk

    draft = "".join(draft_chunks)
    print(f"\n[Catalog] Draft streamed.")

    # 2. Check if critic needed
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

    skip_critic = not merged_profile.get("allergies") and not merged_profile.get("preferences")
    if skip_critic:
        print("[Critic] Skipped — no constraints.")
        return

    # 3. Run critic on full draft
    critique = critic_agent.critique(
        recommendation=draft,
        search_query=search_query,
        profile=merged_profile,
        recipient=recipient or "",
        products=products
    )

    if critique.get("approved"):
        print("[Critic] Approved.")
        return

    # 4. Critic rejected — stream the revision
    issues = critique.get("issues", [])
    suggestion = critique.get("suggestion")
    print(f"[Critic] Issues found: {issues} — streaming revision.")

    yield "\n\n---\n⚠️ *Let me revise that recommendation:*\n\n"

    # Stream revision directly from LLM
    content = (
        f"Original recommendation:\n{draft}\n\n"
        f"Issues found:\n" + "\n".join(f"- {i}" for i in issues) +
        f"\n\nSuggested fix:\n{suggestion or 'Address the issues above.'}"
    )
    yield from chat_stream(
        system=REVISE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
        max_tokens=CLAUDE_MAX_TOKENS_RESPOND,
        model=CLAUDE_MODEL,
    )