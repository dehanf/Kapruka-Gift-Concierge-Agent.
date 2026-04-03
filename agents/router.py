# agents/router.py

import json
import anthropic
from memory.st_memory import ShortTermMemory
from memory.semantic_memory import add_or_update_profile
from agents import catalog_agent


client = anthropic.Anthropic()

ROUTER_SYSTEM_PROMPT = """You are an intent classifier for a Kapruka gift concierge system in Sri Lanka.

Analyze the user's message and extract ALL intents present. There can be 1, 2, or 3 intents in a single message.

INTENTS:
- PREFERENCE_UPDATE: User wants to save/update a recipient's preferences, allergies, or personal info
- SEARCH: User wants to find/search for a gift or product from the catalog
- LOGISTICS: User asks about delivery, location, district, timing, or availability

Respond ONLY with a JSON object in this exact format (no other text, no markdown):
{
  "intents": ["PREFERENCE_UPDATE", "SEARCH", "LOGISTICS"],
  "recipient": "wife",
  "allergies": ["nuts", "dairy"],
  "location": "Kandy",
  "search_query": "nut-free birthday cake",
  "preference_note": "wife is allergic to nuts"
}

Rules:
- "intents" must always be a list, even if only one intent
- Always put PREFERENCE_UPDATE first if present (must save before searching)
- Always put LOGISTICS last if present
- Set fields to null if not mentioned
- "search_query" should be a clean product search string"""

class Router:
    def __init__(self,customer_id : str):
        self.customer_id = customer_id
        self.st_memory = ShortTermMemory()


    def classify_intents(self, user_message: str) -> dict:

        # Get existing history THEN append current message
        history = self.st_memory.get_history()
        messages = history + [{"role": "user", "content": user_message}]

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=300,
            system=ROUTER_SYSTEM_PROMPT,
            messages=messages
        )

        raw = response.content[0].text.strip()

        try:
            result = json.loads(raw)
            if isinstance(result.get("intents"), str):
                result["intents"] = [result["intents"]]
            return result
        except json.JSONDecodeError:
            return {
                "intents": ["SEARCH"],
                "recipient": None,
                "allergies": None,
                "location": None,
                "deadline": None,
                "search_query": user_message,
                "preference_note": None
            }

    def route(self, user_message: str) -> str:

        # 1. Classify first — history doesn't have this message yet
        classification = self.classify_intents(user_message)
        intents = classification.get("intents", ["SEARCH"]) # if no intents ,then search default

        print(f"\n👤 Customer        : {self.customer_id}")
        print(f"🔀 Router Decision : {intents}")
        print(f"📋 Extracted       : {json.dumps(classification, indent=2)}")

        responses = []

        # 2. Run agents
        for intent in intents:

            if intent == "PREFERENCE_UPDATE":
                result = add_or_update_profile(
                    customer_id=self.customer_id,
                    name=classification.get("recipient"),
                    preferences=classification.get("preference_note"),
                    allergies=classification.get("allergies"),
                    location = classification.get("location")
                )
                responses.append(result)

            elif intent == "SEARCH":
                result = catalog_agent.run(
                    customer_id=self.customer_id,
                    recipient=classification.get("recipient"),
                    search_query=classification.get("search_query") or user_message
                )
                responses.append(result)

            elif intent == "LOGISTICS":
                # logistics agent goes here
                pass

        final_response = "\n\n".join(responses)

        # 3. Save BOTH to memory after everything is done
        self.st_memory.add_message("user", user_message)
        self.st_memory.add_message("assistant", final_response)

        return final_response