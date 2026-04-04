import json
import os
from pathlib import Path

_DEFAULT_PATH = str(Path(__file__).resolve().parents[1] / "data" / "recipient_profiles.json")


class SemanticMemory:

    def __init__(self, filepath: str = _DEFAULT_PATH):
        self.filepath = filepath
        self.profiles = {}
        self.load()
    
    def load(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        
        if os.path.exists(self.filepath):
            with open(self.filepath, "r") as f:
                self.profiles = json.load(f)
            print(f"Loaded {len(self.profiles)} recipient profiles.")
        else:
            self.profiles = {}
            print("No profiles found. Starting fresh.")

    def save(self):
        with open(self.filepath, "w") as f:
            json.dump(self.profiles, f, indent=2)
        print(f"Profiles saved to {self.filepath}")

    def add_or_update_profile(self, customer_id: str, name: str, allergies: list = [], preferences: list = [], location: str = ""):
        
        if customer_id not in self.profiles:
            self.profiles[customer_id] = {}
        name = name.lower() 
        
        if name not in self.profiles[customer_id]:
            self.profiles[customer_id][name] = {
                "allergies": [],
                "preferences": [],
                "location": ""
            }
        

        if allergies:
            self.profiles[customer_id][name]["allergies"] = list(
                set(self.profiles[customer_id][name]["allergies"] + allergies)
            )
        if preferences:
            self.profiles[customer_id][name]["preferences"] = list(
                set(self.profiles[customer_id][name]["preferences"] + preferences)
            )
        if location:
            self.profiles[customer_id][name]["location"] = location
        
        self.save()
        print(f"Profile updated: {name}")

    def get_profile(self,customer_id:str, name: str) -> dict:
        name = name.lower()
        if customer_id in self.profiles:
            if name in self.profiles[customer_id]:
                return self.profiles[customer_id][name]
            else:
                print(f"No profile found for: {name}")

        else:
            print(f"No customer found for: {customer_id}")
            return {}


# Module-level singleton used by router.py
_memory = SemanticMemory()

def add_or_update_profile(customer_id: str, name: str, allergies: list = None, preferences: list = None, location: str = "") -> str:
    if not name:
        return "No recipient name provided — profile not updated."
    # "self" means the customer is buying for themselves — store under their own name
    resolved_name = customer_id if name.lower() == "self" else name
    _memory.add_or_update_profile(
        customer_id=customer_id,
        name=resolved_name,
        allergies=allergies or [],
        preferences=[preferences] if isinstance(preferences, str) and preferences else (preferences or []),
        location=location or ""
    )
    display = "your" if name.lower() == "self" else f"{resolved_name}'s"
    return f"Got it — I've saved {display} preferences."

def get_profile(customer_id: str, name: str) -> dict:
    return _memory.get_profile(customer_id, name) or {}
