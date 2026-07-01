from pymongo import MongoClient
from datetime import datetime
import json
import os

# Load config to get URI
def load_config():
    if os.path.exists("config.json"):
        with open("config.json", "r") as f:
            return json.load(f)
    return {}

config = load_config()
uri = config.get("MONGO_URI", "mongodb://localhost:27017/")

client = MongoClient(uri)
db = client.get_database("cybercourt")
users_col = db.get_collection("users")

print("--- Inspecting Timestamps ---")
for user in users_col.find({}, {"username": 1, "created_at": 1, "role": 1}):
    c_at = user.get("created_at")
    print(f"User: {user.get('username')} | Role: {user.get('role')}")
    print(f"  Raw: {c_at!r}")
    print(f"  Type: {type(c_at)}")
    if isinstance(c_at, datetime):
        print(f"  Tzinfo: {c_at.tzinfo}")
    print("-" * 30)
