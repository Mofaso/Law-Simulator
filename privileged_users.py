import argparse
import secrets
import string
import json
from datetime import datetime, timezone
from pymongo import MongoClient
import bcrypt

# ---------- LOAD CONFIG ----------
with open("config.json", "r") as f:
    config = json.load(f)

MONGO_URI = config["MONGO_URI"]
DB_NAME = "CyberCourtDB"

# ---------- ROLE PREFIX ----------
ROLE_PREFIX = {
    "admin": "ADM",
    "judge": "JDG",
    "lawmaker": "LMW",
    "simulator": "SIM"
}

# ---------- HELPERS ----------
def generate_system_id(role, users_collection):
    prefix = ROLE_PREFIX.get(role)
    if not prefix:
        return None
    count = users_collection.count_documents({"role": role})
    return f"{prefix}{count + 1:03d}"

def generate_random_password(length=12):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    while True:
        pwd = ''.join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in pwd)
            and any(c.isupper() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in "!@#$%^&*()-_=+" for c in pwd)
        ):
            return pwd

def create_user_record(role, username, email, users_collection):
    s_id = generate_system_id(role, users_collection)
    password_plain = generate_random_password()

    hashed = bcrypt.hashpw(password_plain.encode(), bcrypt.gensalt())

    doc = {
        "username": username,
        "email": email,
        "password": hashed,
        "role": role,
        "s_id": s_id,
        "created_at": datetime.now(timezone.utc)
    }

    users_collection.insert_one(doc)
    return s_id, password_plain

# ---------- MAIN ----------
def main(export_file=None):
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    users = db["users"]

    pairs = [
        ("admin", "admin01", "admin01@example.com"),
        ("judge", "judge01", "judge01@example.com"),
        ("lawmaker", "lawmaker01", "lawmaker01@example.com"),
        ("simulator", "simulator01", "simulator01@example.com"),
    ]

    exports = []

    for role, username, email in pairs:
        existing = users.find_one({"username": username})
        if existing:
            print(f"[!] {username} already exists — skipping.")
            exports.append((role, username, existing.get("s_id"), "<already exists>"))
            continue

        s_id, pwd = create_user_record(role, username, email, users)
        print(f"[✔] Created {role}: {username} ({s_id}) — password (ONE-TIME): {pwd}")
        exports.append((role, username, s_id, pwd))

    if export_file:
        with open(export_file, "w", encoding="utf-8") as f:
            f.write("role,username,s_id,password\n")
            for r, u, s, p in exports:
                f.write(f"{r},{u},{s},{p}\n")
        print(f"[✔] Exported credentials to {export_file} — DELETE after use.")

# ---------- ENTRY ----------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", help="Export credentials (temporary)")
    args = parser.parse_args()
    main(export_file=args.export)
