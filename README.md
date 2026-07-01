# ⚖️ CyberCourt — AI-Powered Legal Simulation Platform

A full-stack intelligent legal analysis platform that simulates 
the real-world impact of proposed laws using Gemini AI, 
embedding-based law validation, and dynamic societal impact modeling.

---

## 🚀 Key Features

- **CLEV (Constitutional Law Existence Validator)** — detects if a 
  proposed law already exists using text-embedding-004 + cosine 
  similarity (85% threshold), preventing duplicate legislation
- **AI Legal Simulation** — Gemini 2.5 Flash analyzes any law and 
  returns positives, negatives, risk score (0–10), and auto-generates 
  safer alternatives for high-risk proposals
- **Dynamic Impact Engine** — NLP domain detection across 6 domains 
  (corporate/education/environment/tech/military/society) with 
  per-group sentiment scoring and personality bias modeling
- **Explainability Layer** — every AI decision is recorded and 
  accessible via admin audit dashboard
- **Multi-Role RBAC** — Admin, Judge, Lawmaker, Simulator, User 
  roles with system IDs and bcrypt auth
- **30+ laws analyzed** including high-complexity critical legislation

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask, Flask-Login |
| AI | Gemini 2.5 Flash/Pro, text-embedding-004 |
| Database | MongoDB |
| Auth | bcrypt, RBAC, Session management |
| Packaging | PyInstaller (Windows .exe) |



## ⚙️ Setup

1. Clone the repo
2. Copy `config.template.json` → `config.json` and add your keys
3. `pip install -r requirements.txt`
4. `python app.py`

---

## 🏆 Recognition

Personally appreciated by law faculty at Vel Tech University 
for practical utility in policy evaluation and legal education.
