# agents/router.py

import json
from memory.st_memory import ShortTermMemory
from memory.semantic_memory import add_or_update_profile
from agents import catalog_agent, logistics_agent
from utils.config import CLAUDE_MODEL, CLAUDE_MAX_TOKENS
from utils.prompts import ROUTER_SYSTEM_PROMPT
from infrastructure.llm.client import chat


class Router:
    def __init__(self,customer_id : str):
        self.customer_id = customer_id
        self.st_memory = ShortTermMemory()


    def classify_intents(self, user_message: str) -> dict:

        # Get existing history THEN append current message
        history = self.st_memory.get_history()
        messages = history + [{"role": "user", "content": user_message}]

        raw = chat(
            system=ROUTER_SYSTEM_PROMPT,
            messages=messages,
            max_tokens=CLAUDE_MAX_TOKENS,
            model=CLAUDE_MODEL,
        )

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

        print(f"Customer        : {self.customer_id}")
        print(f"Router Decision : {intents}")
        print(f"Extracted       : {json.dumps(classification, indent=2)}")

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
                result = logistics_agent.run(
                    location=classification.get("location"),
                    deadline=classification.get("deadline"),
                    tracking_code=classification.get("tracking_code")
                )
                responses.append(result)

        final_response = "\n\n".join(responses)

        # 3. Save BOTH to memory after everything is done
        self.st_memory.add_message("user", user_message)
        self.st_memory.add_message("assistant", final_response)

        return final_response