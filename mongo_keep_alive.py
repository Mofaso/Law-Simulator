# mongo_keep_alive.py
import pymongo
import time
from datetime import datetime

# --- Replace this with your actual MongoDB URI ---
MONGO_URI = "mongodb://localhost:27017/"

def ping_mongo():
    try:
        client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.server_info()  # forces connection
        print(f"[{datetime.now()}] MongoDB Keep-Alive Ping Successful.")
    except Exception as e:
        print(f"[{datetime.now()}] Keep-Alive Failed: {e}")

if __name__ == "__main__":
    ping_mongo()
