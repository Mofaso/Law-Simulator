import json
import io
import sys
from pymongo import MongoClient
from werkzeug.security import check_password_hash
import bcrypt

# Fix Windows console encoding
if sys.stdout:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    with open("config.json", "r") as f:
        config = json.load(f)
except Exception as e:
    print(f"❌ Error loading config.json: {e}")
    sys.exit(1)

client = MongoClient(config["MONGO_URI"])
db = client["CyberCourtDB"]
users = db["users"]

print("🔍 Testing Admin Authentication...")
admin = users.find_one({"role": "admin"})

if not admin:
    print("❌ No admin user found!")
    sys.exit(1)

print(f"Found Admin: {admin.get('username')} (s_id: {admin.get('s_id')})")

password_attempt = "Admin@123"
stored_password = admin.get("password")

print(f"Stored Password Type: {type(stored_password)}")
print(f"Stored Password Value (repr): {repr(stored_password)}")

# Test 1: Werkzeug
print("\n🧪 Test 1: Werkzeug check_password_hash")
try:
    # Werkzeug expects string, but stored might be bytes
    # It attempts to handle bytes but let's see why it fails
    if isinstance(stored_password, bytes):
         print("   (converting bytes to string for werkzeug test)")
         stored_password_str = stored_password.decode('utf-8')
    else:
         stored_password_str = stored_password
         
    if check_password_hash(stored_password_str, password_attempt):
        print("✅ Werkzeug Match: SUCCESS")
    else:
        print("❌ Werkzeug Match: FAILED")
except Exception as e:
    print(f"❌ Werkzeug Exception: {e}")

# Test 2: Bcrypt
print("\n🧪 Test 2: bcrypt.checkpw")
try:
    if isinstance(stored_password, str):
        print("   (converting string to bytes for bcrypt test)")
        stored_password_bytes = stored_password.encode('utf-8')
    else:
        stored_password_bytes = stored_password

    if bcrypt.checkpw(password_attempt.encode('utf-8'), stored_password_bytes):
        print("✅ Bcrypt Match: SUCCESS")
    else:
        print("❌ Bcrypt Match: FAILED")
        
except Exception as e:
    print(f"❌ Bcrypt Exception: {e}")
