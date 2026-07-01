from pymongo import MongoClient
from urllib.parse import quote_plus

username = quote_plus("CyberCourt")         # Your Atlas username
password = quote_plus("Cyber1234")         # New password you just set

uri = "mongodb+srv://mohantmr4114_db_user:1234qwerasdf12@cluster0.u0d2ipe.mongodb.net/?appName=Cluster0"

client = MongoClient(uri)

try:
    print(client.server_info())  # 🔥 Will succeed if credentials are correct
    print("✅ Connected successfully to MongoDB Atlas")
except Exception as e:
    print("❌ Connection failed:", e)
