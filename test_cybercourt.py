import requests
from bs4 import BeautifulSoup

BASE_URL = "http://127.0.0.1:5000"

# ---------------- Session ---------------- #
session = requests.Session()

# ---------------- Signup ---------------- #
signup_data = {
    "username": "testuser123",
    "password": "Test@1234",
    "email": "testuser@example.com"
}

resp = session.post(f"{BASE_URL}/signup", data=signup_data, allow_redirects=True)
if "Signup successful" in resp.text or resp.status_code == 200:
    print("✅ Signup worked")
else:
    print("❌ Signup might have failed")

# ---------------- Login ---------------- #
login_data = {
    "username": "testuser123",
    "password": "Test@1234"
}

resp = session.post(f"{BASE_URL}/login", data=login_data, allow_redirects=True)
if "AI Judge Simulator" in resp.text:
    print("✅ Login worked and redirected to simulator")
else:
    print("❌ Login failed or did not redirect")

# ---------------- Submit a Law ---------------- #
law_data = {
    "case": "All citizens must recycle 50% of household waste."
}

resp = session.post(f"{BASE_URL}/simulator", data=law_data)
if "Positives" in resp.text or "negatives" in resp.text.lower():
    print("✅ Simulator returned verdict")
else:
    print("❌ Simulator verdict not generated")

# ---------------- Logout ---------------- #
resp = session.get(f"{BASE_URL}/logout", allow_redirects=True)
if "Login" in resp.text:
    print("✅ Logout successful")
else:
    print("❌ Logout failed")
