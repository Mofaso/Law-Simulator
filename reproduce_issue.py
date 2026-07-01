import json
import sys
import io
import bcrypt
from pymongo import MongoClient
from flask_login import UserMixin

# Mock User class from app.py
class User(UserMixin):
    def __init__(self, user_dict):
        self.id = str(user_dict.get("_id"))
        self.username = user_dict.get("username")
        self.email = user_dict.get("email", "")
        self.role = user_dict.get("role", "user")

# Fix Windows console
if sys.stdout:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    with open("config.json", "r") as f:
        config = json.load(f)
except Exception as e:
    print(f"Error loading config: {e}")
    sys.exit(1)

client = MongoClient(config["MONGO_URI"])
db = client["CyberCourtDB"]
users_collection = db["users"]

# Variables simulating the request
role = "admin"
s_id = "ADM001"
password = "Admin@123"

print(f"🔍 Attempting simulated login for Role: {role}, ID: {s_id}")

try:
    user = users_collection.find_one({"s_id": s_id, "role": role})

    if not user:
        print("❌ User not found in DB")
        sys.exit(1)

    print(f"✅ User found: {user.get('username')}")

    stored_pw = user.get("password")
    if isinstance(stored_pw, str):
        stored_pw = stored_pw.encode('utf-8')

    print(f"   Stored Password Type: {type(stored_pw)}")
    
    try:
        is_valid = bcrypt.checkpw(password.encode('utf-8'), stored_pw)
        print(f"   bcrypt check result: {is_valid}")
    except Exception as e:
        print(f"❌ bcrypt check FAILED with error: {e}")
        raise e # Re-raise to verify crash

    if is_valid:
        print("   Password valid.")
        print("   Initializing User object...")
        try:
            user_obj = User(user)
            print("✅ User object created successfully.")
            print(f"   User ID: {user_obj.id}")
            print(f"   User Role: {user_obj.role}")
        except Exception as e:
            print(f"❌ User object creation FAILED: {e}")
            raise e
    else:
        print("❌ Password invalid.")

except Exception as e:
    print("\n💥 CRASH DETECTED (This is likely causing the 500 error):")
    import traceback
    traceback.print_exc()
