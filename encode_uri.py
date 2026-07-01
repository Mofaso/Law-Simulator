from urllib.parse import quote_plus

raw_username = "CyberCourt"              # put your Atlas username
raw_password = "1234qwerasdf@M1d"        # put your Atlas password

username = quote_plus(raw_username)
password = quote_plus(raw_password)

print("Encoded username:", username)
print("Encoded password:", password)

uri = f"mongodb+srv://{username}:{password}@cluster0.mongodb.net/cybercourt?retryWrites=true&w=majority"
print("✅ Use this URI in your app.py:\n", uri)
