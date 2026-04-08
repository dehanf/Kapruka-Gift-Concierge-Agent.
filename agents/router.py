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
from pydantic import BaseModel
from typing import Literal


class RouterOutput(BaseModel):
    intents: list[Literal["SEARCH", "LOGISTICS", "PREFERENCE_UPDATE"]]
    allergies: dict
    preferences: dict
    search_recipient: str | list | None
    location: str | None
    deadline: str | None
    search_query: str | None
    tracking_code: str | None


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
            json_mode=True,

        )

        #structured output extraction - json format
        clean = raw.strip()
        start = clean.find("{")
        end = clean.rfind("}") + 1
        if start != -1 and end > start:
            clean = clean[start:end]

        try:
            result = json.loads(clean)
            validated = RouterOutput(**result) #pydantic validation 
            result = validated.model_dump()
            if isinstance(result.get("intents"), str):
                result["intents"] = [result["intents"]]
            if not isinstance(result.get("allergies"), dict):
                result["allergies"] = {}
            if not isinstance(result.get("preferences"), dict):
                result["preferences"] = {}
            return result

        except (json.JSONDecodeError, ValueError): #value errors for pydantic errors
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
        location = classification.get("location") or "" 
        old_profile = {
                "allergies": {},
                "preferences": {},
                "location": {}
            }

        new_profile = {
                "allergies": {},
                "preferences": {},
                "location": {}
                }

        # 3. Load old profile
        recipient = classification.get("search_recipient")
        if isinstance(recipient, list) and len(recipient) > 1:
            # Multiple recipients — merge all profiles


            for name in recipient:
                # old profile
                p = get_profile(self.customer_id, name) or {}
                old_profile['allergies'][name] = p.get("allergies",[])
                old_profile['preferences'][name] = p.get("preferences",[])
                old_profile['location'][name] = p.get("location", "")

                # new profile
                new_profile['allergies'][name] = allergies_dict.get(name,[])
                new_profile['preferences'][name] = preferences_dict.get(name,[])
                new_profile['location'][name] = location
            

            recipient = ", ".join(recipient)  # "daughter, wife, son" 

        else:
            # Single recipient
            if isinstance(recipient, list):
                recipient = recipient[0] if recipient else None
            p = get_profile(self.customer_id, recipient) or {}
            old_profile['allergies'][recipient] = p.get("allergies",[])
            old_profile['preferences'][recipient] = p.get("preferences",[])
            old_profile['location'][recipient] = p.get("location", "")
            new_profile['allergies'][recipient] = allergies_dict.get(recipient,[])
            new_profile['preferences'][recipient] = preferences_dict.get(recipient,[])
            new_profile['location'][recipient] = location 

        
        print("old profile is" ,old_profile)
        print("new profile is",new_profile)

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
                    "allergies": allergies_dict.get(name, {}),
                    "preferences": preferences_dict.get(name, {}),
                    "location": classification.get("location") or ""
                })
                t.daemon = True
                t.start()
                yield "<<PREF_SAVING>>"

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
            yield "<<LOGISTICS>>"
                
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
                    if chunk != "<<CLEAR>>":
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