import json
import concurrent.futures
import threading
from memory.st_memory import ShortTermMemory
from memory.semantic_memory import add_or_update_profile, get_profile
from agents import catalog_agent, logistics_agent
from utils.config import CLAUDE_MODEL_CLASSIFY, CLAUDE_MAX_TOKENS_CLASSIFY
from utils.prompts import ROUTER_SYSTEM_PROMPT
from infrastructure.llm.client import chat
from memory.lt_memory import precompute_embedding
import time



class Router:
    def __init__(self, customer_id: str):
        self.customer_id = customer_id
        self.st_memory = ShortTermMemory()

    def classify_intents(self, user_message: str) -> dict:

        history = self.st_memory.get_history()
        messages = history + [{"role": "user", "content": user_message}]

        raw = chat(
            system=ROUTER_SYSTEM_PROMPT,
            messages=messages,
            max_tokens=CLAUDE_MAX_TOKENS_CLASSIFY,
            model=CLAUDE_MODEL_CLASSIFY,
        )

        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
            clean = clean.strip()

        try:
            result = json.loads(clean)
            if isinstance(result.get("intents"), str):
                result["intents"] = [result["intents"]]
            if not isinstance(result.get("allergies"), dict):
                result["allergies"] = {}
            if not isinstance(result.get("preferences"), dict):
                result["preferences"] = {}
            return result

        except json.JSONDecodeError:
            return {
                "intents": ["SEARCH"],
                "allergies": {},
                "preferences": {},
                "search_recipient": None,
                "location": None,
                "deadline": None,
                "search_query": user_message,
                "tracking_code": None
            }

    def route_stream(self, user_message: str):
        """Streaming version of route() — yields chunks for SEARCH responses."""

        # 1. Classify and embedding parallely to enhance response time
        start = time.time()
        with concurrent.futures.ThreadPoolExecutor() as ex:

            print('classifying thread pool starts...')
            classify_future = ex.submit(self.classify_intents,user_message)
            encode_future = ex.submit(precompute_embedding,user_message)
            classification = classify_future.result()
            query_vector = encode_future.result()
        end = time.time()

        print(f'classifying thread pool ends... : {end-start}s')
        

        intents = classification.get("intents", ["SEARCH"])

        print(f"Customer        : {self.customer_id}")
        print(f"Router Decision : {intents}")
        print(f"Extracted       : {json.dumps(classification, indent=2)}")

        # 2. allergies_dict and preferences_dict still needed for PREFERENCE_UPDATE
        allergies_dict = classification.get("allergies") or {}
        preferences_dict = classification.get("preferences") or {}

        # 3. Load old profile
        recipient = classification.get("search_recipient")
        if isinstance(recipient, list) and len(recipient) > 1:
            # Multiple recipients — merge all profiles
            merged_allergies = []
            merged_preferences = []
            merged_location = ""
            merged_new_allergies = []
            merged_new_preferences = []

            for name in recipient:
                # old profile
                p = get_profile(self.customer_id, name) or {}
                merged_allergies += p.get("allergies", [])
                merged_preferences += p.get("preferences", [])
                merged_location = merged_location or p.get("location", "")
                # new profile
                merged_new_allergies += allergies_dict.get(name, [])
                merged_new_preferences += preferences_dict.get(name, [])

            old_profile = {
                "allergies": list(set(merged_allergies)),
                "preferences": list(set(merged_preferences)),
                "location": merged_location
            }
            new_profile = {
                "allergies": list(set(merged_new_allergies)), 
                "preferences": list(set(merged_new_preferences)), 
                "location": classification.get("location") or ""
            }
            recipient = ", ".join(recipient)  # "daughter, wife, son" 

        else:
            # Single recipient
            if isinstance(recipient, list):
                recipient = recipient[0] if recipient else None
            old_profile = get_profile(self.customer_id, recipient) if recipient else {}

            #merge old and new 
            new_profile = {
                "allergies": allergies_dict.get(recipient, []) if recipient else [],
                "preferences": preferences_dict.get(recipient, []) if recipient else [],
                "location": classification.get("location") or ""
            }

        # Initialize before if blocks
        all_recipients = set()
        full_response_chunks = []

        # 4. PREFERENCE_UPDATE — fire and forget
        if "PREFERENCE_UPDATE" in intents:
            all_recipients = set(list(allergies_dict.keys()) + list(preferences_dict.keys()))
            print('preference update thread starts...')
            for name in all_recipients:
                t = threading.Thread(target=add_or_update_profile, kwargs={
                    "customer_id": self.customer_id,
                    "name": name,
                    "allergies": allergies_dict.get(name, []),
                    "preferences": preferences_dict.get(name, []),
                    "location": classification.get("location") or ""
                })
                t.daemon = True
                t.start()

        """To make efficient the response we're using a strategy where
        the logistic intent is fired then after that search intent is fired and streamed
        after that logistic response is joined
        
"""     
        #initializing them before in case executor gets failed
        logistics_future = None   
        logistics_executor = None      


        # 5. Firing logistics in background
        if "LOGISTICS" in intents:
            logistics_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            print('logistic intent thread fired...')

            logistics_future = logistics_executor.submit(
                logistics_agent.run,
                location=classification.get("location"),
                deadline=classification.get("deadline"),
                tracking_code=classification.get("tracking_code")
            )
                
        try:
            # 6. Stream search — logistics already running in background
            if "SEARCH" in intents:
                for chunk in catalog_agent.run_stream(
                    recipients=all_recipients,
                    search_query=classification.get("search_query") or user_message,
                    old_profile=old_profile,
                    new_profile=new_profile,
                    query_vector = query_vector
                ):
                    full_response_chunks.append(chunk)
                    yield chunk


            # 7. Logistics already done by now — yields instantly
            if "LOGISTICS" in intents and logistics_future:
                logistics_result = logistics_future.result()
                yield "\n\n" + logistics_result
                full_response_chunks.append("\n\n" + logistics_result)
        
        finally:
            if logistics_executor:
                logistics_executor.shutdown(wait=False)
                print('logistics_executor shut down.')



        # 8. Save to memory
        full_response = "".join(full_response_chunks)
        pref_msg = f"Got it — I'm updating preferences for {', '.join(all_recipients)}.\n\n" if "PREFERENCE_UPDATE" in intents else ""
        self.st_memory.add_message("user", user_message)
        self.st_memory.add_message("assistant", pref_msg + full_response)