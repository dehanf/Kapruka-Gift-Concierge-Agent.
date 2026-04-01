import json
import os


class SemanticMemory:

    def __init__(self,filepath: str = "../data/recipient_profiles.json"):
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
