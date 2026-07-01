import sys, io
import json
from pymongo import MongoClient
import bcrypt
import datetime

# Fix Windows console encoding
if sys.stdout:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Load config
try:
    with open("config.json", "r") as f:
        config = json.load(f)
except FileNotFoundError:
    print("❌ config.json not found!")
    exit(1)

client = MongoClient(config["MONGO_URI"])
db = client["CyberCourtDB"]
users = db["users"]

print("🔍 Checking admin account status...")

# Check if "admin" user exists
admin_user = users.find_one({"username": "admin"})
s_id = None

if admin_user:
    s_id = admin_user.get("s_id")
    if not s_id:
        print("⚠️ Found 'admin' user but missing System ID (s_id). Fixing...")
        
        # Find a free s_id
        existing_ids = [u.get("s_id") for u in users.find({"role": "admin"}) if u.get("s_id")]
        count = 1
        while True:
            candidate = f"ADM{count:03d}"
            if candidate not in existing_ids:
                s_id = candidate
                break
            count += 1
            
        users.update_one({"_id": admin_user["_id"]}, {"$set": {"s_id": s_id}})
        print(f"✅ Fixed 'admin' user. Assigned System ID: {s_id}")
    else:
        print(f"ℹ️ 'admin' user already exists with System ID: {s_id}")

    # Reset password ensuring it matches what we tell the user
    password = "Admin@123"
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    users.update_one({"_id": admin_user["_id"]}, {"$set": {"password": hashed_password}})
    print(f"🔄 Password reset to ensure access.")

else:
    print("🆕 Creating new admin user...")
    
    # Generate ID
    existing_ids = [u.get("s_id") for u in users.find({"role": "admin"}) if u.get("s_id")]
    count = 1
    while True:
        candidate = f"ADM{count:03d}"
        if candidate not in existing_ids:
            s_id = candidate
            break
        count += 1

    password = "Admin@123"
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

    new_admin = {
        "username": "admin",
        "email": "admin@cybercourt.com",
        "password": hashed_password,
        "role": "admin",
        "s_id": s_id,
        "created_at": datetime.datetime.now()
    }
    
    users.insert_one(new_admin)
    print("✅ Admin user CREATED successfully")

print("\n" + "=" * 40)
print(f"🔑 ADMIN LOGIN CREDENTIALS")
print("=" * 40)
print(f"➡️  Role      : Admin")
print(f"➡️  System ID : {s_id}  <-- USE THIS TO LOGIN")
print(f"➡️  Password  : Admin@123")
print("=" * 40)
