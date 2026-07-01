# ---------------- PART 1 (FIXED) ----------------
import sys, io

if sys.stdout:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr:
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os
import sys
import json
import secrets
import re
import time
import socket
import bcrypt
import string
import math
from datetime import datetime, timedelta, timezone

# Define IST timezone
IST = timezone(timedelta(hours=5, minutes=30))

from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from pymongo import MongoClient

from pymongo.errors import ServerSelectionTimeoutError
from bson import ObjectId
# from dotenv import load_dotenv # No longer needed
from textblob import TextBlob
import google.generativeai as genai
import google.api_core.exceptions # Import specific exception type

# ---------------- Helper: resource_path for PyInstaller compatibility ----------------
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        base_path = sys._MEIPASS  # PyInstaller temp folder
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ---------------- Flask App Setup ----------------
app = Flask(
    __name__,
    template_folder=resource_path("templates"),
    static_folder=resource_path("static")
)
app.debug = True # Set to False in production
app.config['TEMPLATES_AUTO_RELOAD'] = True
# Secret key will be loaded from config.json
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

# ---------------- Load environment (Config File) ----------------
# Load config file once
def load_config():
    config_path = resource_path("config.json")
    if not os.path.exists(config_path):
        print(f"❌ CRITICAL: config.json not found at {config_path}")
        print("Please create config.json with MONGO_URI, GENAI_KEY, and FLASK_SECRET_KEY.")
        sys.exit(1)
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"❌ CRITICAL: config.json at {config_path} is not valid JSON.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ CRITICAL: Error reading config.json: {e}")
        sys.exit(1)

config = load_config()

GENAI_KEY = config.get("GENAI_KEY")
MONGO_URI = config.get("MONGO_URI")
app.secret_key = config.get("FLASK_SECRET_KEY")

if not MONGO_URI or not app.secret_key:
    print("❌ CRITICAL: MONGO_URI and FLASK_SECRET_KEY must be set in config.json.")
    sys.exit(1)

# ---------------- Gemini AI Setup ----------------
# Global variable for the model instance
model = None

if not GENAI_KEY:
    print("⚠️ WARNING: GENAI_KEY is missing from config.json. AI features will use fallback mode.")
else:
    try:
        print("🔧 Configuring Gemini with API key...")
        genai.configure(api_key=GENAI_KEY)
    except Exception as e:
        print(f"❌ CRITICAL: Failed to configure Gemini API: {e}")
        print("   Make sure the API key in config.json is correct and valid.")
        GENAI_KEY = None # Clear key if configuration failed

# --- NEW, OPTIMIZED FUNCTION (Version 4) ---
def initialize_gemini_model():
    """
    Tries to initialize a valid Gemini model from a list of preferred names.
    This list is optimized based on the user's specific available models.
    """
    # --- NEW: Prioritizing specific 2.5 models, then -latest aliases ---
    preferred_models = [
        "gemini-2.5-flash",     # Specific, newest, fastest (We know you have this)
        "gemini-2.5-pro",       # Specific, newest, smartest (We know you have this)
        "gemini-flash-latest",  # Alias, stable, fastest (We know you have this)
        "gemini-pro-latest",    # Alias, stable, smartest (We know you have this)
        "gemini-pro"            # Base model, just in case all else fails
    ]
    # -----------------------------------------------------------

    for name in preferred_models:
        try:
            print(f"🔍 Trying to initialize model: {name}")

            # Step 1: Proactively check if the model exists.
            # This check uses the "models/" prefix.
            genai.get_model(f"models/{name}")
            # Step 2: If Step 1 succeeds, create the GenerativeModel instance.
            # This one does NOT use the "models/" prefix.
            model_instance = genai.GenerativeModel(name)
            print(f"✅ Successfully initialized and verified model: {name}")
            return model_instance # Return the initialized model object
        except google.api_core.exceptions.NotFound as e:
            # This should not happen now, but good to keep
            print(f"⚠️ Model {name} not found (404 Error). Trying next...")
        except google.api_core.exceptions.PermissionDenied as e:
            print(f"⚠️ Permission Denied for model {name}: {e}")
            print("   Check if the API key is valid and has permissions for this model. Trying next...")
        except Exception as e:
            # Catch other potential errors
            print(f"⚠️ Error initializing model {name}: {e}. Trying next...")

    print("❌ No valid Gemini models could be initialized after trying all options. Using fallback mode.")
    return None
# --- END OF OPTIMIZED FUNCTION ---

# Initialize the model during app startup
if GENAI_KEY: # Only try to initialize if key was set and configuration didn't fail
    try:
        print("🚀 Initializing Gemini model...")
        model = initialize_gemini_model() # Assign to the global variable
        if model is None:
             print("   Gemini features will use fallback for all requests.")
    except Exception as e:
        # Catch any unexpected errors during the initialization process
        print(f"⚠️ Unexpected critical error during Gemini initialization: {e}")
        model = None # Ensure model is None if anything goes wrong

# ---------------- Explainability Init ----------------
try:
    import explainability
    print("🕵️ Initializing Explainability Layer...")
    explainability.init_recorder(model, GENAI_KEY)
except Exception as e:
    print(f"⚠️ Explainability Init Failed: {e}")




# ---------------- MongoDB Setup ----------------
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.server_info()
    print("✅ Connected to MongoDB.")
    db = client.get_database("cybercourt") # You can change this DB name
    users_collection = db.get_collection("users")
    history_collection = db.get_collection("simulation_history")
except ServerSelectionTimeoutError:
    print(f"❌ CRITICAL: Could not connect to MongoDB at {MONGO_URI.split('@')[-1]}. Server timed out.")
    print("Please ensure MongoDB is running, accessible, and IP is whitelisted.")
    sys.exit(1)
except Exception as e:
    print(f"❌ CRITICAL: An error occurred during MongoDB setup: {e}")
    sys.exit(1)

# ---------------- Password Verification Helper ----------------
def verify_password(plain_password: str, stored_hash) -> bool:
    """
    Verify password using bcrypt.
    Handles MongoDB-stored bytes or strings safely.
    """
    if not plain_password or not stored_hash:
        return False

    if isinstance(stored_hash, str):
        stored_hash = stored_hash.encode("utf-8")

    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        stored_hash
    )

# ---------------- SYSTEM ID GENERATOR (MOVED UP) ----------------
# This must be defined BEFORE it is called in auto_create_initial_admin
ROLE_PREFIX = {
    "admin": "ADM",
    "judge": "JDG",
    "lawmaker": "LMW",
    "simulator": "SIM"
}

def generate_system_id(role):
    """Generate next system ID based on role count."""
    prefix = ROLE_PREFIX.get(role)
    if not prefix:
        return None  # user has no system id

    count = users_collection.count_documents({"role": role})
    return f"{prefix}{count + 1:03d}"


# -------------------- AUTO-CREATE FIRST ADMIN (ONLY ONCE) --------------------
def auto_create_initial_admin():
    """Create the very first admin automatically on first server startup."""
    admin_exists = users_collection.find_one({"role": "admin"})

    if admin_exists:
        print("✔ Admin already exists. Skipping initial admin creation.")
        return

    print("⚠ No admin found. Creating FIRST ADMIN automatically...")

    # Default first admin credentials
    first_admin_username = "superadmin"
    first_admin_password = "Admin@123"   # You can change this
    first_admin_email = "admin@system.local"

    # Generate s_id: ADM001
    # Now this works because generate_system_id is defined above!
    s_id = generate_system_id("admin")

    # Hash password
    hashed_pw = bcrypt.hashpw(first_admin_password.encode(), bcrypt.gensalt())

    # Insert admin into DB
    users_collection.insert_one({
        "username": first_admin_username,
        "password": hashed_pw,
        "email": first_admin_email,
        "role": "admin",
        "s_id": s_id,
        "created_at": datetime.now()
    })

    print("✅ FIRST ADMIN CREATED SUCCESSFULLY!")
    print(f"   Username: {first_admin_username}")
    print(f"   System ID: {s_id}")
    print(f"   Password: {first_admin_password}")
    print("   (Please store these credentials securely.)")

# Call auto-creator (Now safe to call)
auto_create_initial_admin()


# ---------------- CLEV (Constitutional Law Existence Validator) ----------------
# MVP: In-memory store of laws and embeddings
LAWS_DB_PATH = resource_path("laws_db.json")
law_embeddings = [] # List of {law_id, title, summary, embedding, text}

def load_laws_db():
    if not os.path.exists(LAWS_DB_PATH):
        print(f"ℹ️ CLEV: {LAWS_DB_PATH} not found. Creating empty DB.")
        return []
    try:
        with open(LAWS_DB_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ CLEV: Error loading laws DB: {e}")
        return []

def get_embedding(text):
    """Generate embedding using Gemini API."""
    if not GENAI_KEY:
        print("⚠️ CLEV: No GENAI_KEY, cannot generate embeddings.")
        return None
    try:
        # caching or batching could be added here for optimization
        # using 'models/embedding-001' or 'models/text-embedding-004'
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_document",
            title="Constitutional Law"
        )
        return result['embedding']
    except Exception as e:
        print(f"❌ CLEV: Embedding error: {e}")
        return None

def initialize_clev():
    """Load laws and pre-compute embeddings."""
    global law_embeddings
    print("🔐 Initializing CLEV (Constitutional Law Existence Validator)...")
    laws = load_laws_db()
    
    count = 0
    for law in laws:
        # In a real app, we'd cache these embeddings to disk/DB
        emb = get_embedding(law["text"])
        if emb:
            law_entry = law.copy()
            law_entry["embedding"] = emb
            law_embeddings.append(law_entry)
            count += 1
            # Rate limit handling (simple sleep for MVP)
            time.sleep(0.5) 
            
    print(f"✅ CLEV initialized with {count} laws.")

def cosine_similarity(v1, v2):
    """Compute cosine similarity between two vectors."""
    if not v1 or not v2: return 0.0
    
    dot_product = sum(a*b for a,b in zip(v1, v2))
    magnitude1 = math.sqrt(sum(a*a for a in v1))
    magnitude2 = math.sqrt(sum(b*b for b in v2))
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
        
    return dot_product / (magnitude1 * magnitude2)

@explainability.explainable("clev_validation")
def validate_law_existence(user_text, threshold=0.85):
    """
    Check if user_text matches any existing law.
    Returns: (is_blocked, match_data, status_tag)
    """
    if not law_embeddings:
        return False, None, "CLEV_OFFLINE"

    user_emb = get_embedding(user_text)
    if not user_emb:
        return False, None, "EMBEDDING_FAILED"

    best_match = None
    best_score = -1

    for law in law_embeddings:
        score = cosine_similarity(user_emb, law["embedding"])
        if score > best_score:
            best_score = score
            best_match = law

    if best_score >= threshold:
        # Existing law detected -> BLOCK
        return True, {
            "law_id": best_match["law_id"],
            "title": best_match["title"],
            "summary": best_match["summary"],
            "similarity_score": round(best_score * 100, 1),
            "match_text": best_match["text"][:200] + "..."
        }, "EXISTING_LAW"
    
    return False, None, "NEW_LAW"

# Initialize CLEV on startup (in background thread ideally, but blocking is safer for MVP correctness)
if GENAI_KEY:
    # We do this in a thread to not block the whole app startup if it takes time
    import threading
    threading.Thread(target=initialize_clev, daemon=True).start()



# ---------------- Flask-Login Setup ----------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message_category = "info"

class User(UserMixin):
    def __init__(self, user_dict):
        self.id = str(user_dict.get("_id"))
        self.username = user_dict.get("username")
        self.email = user_dict.get("email", "")
        self.role = user_dict.get("role", "user")  # NEW


@login_manager.user_loader
def load_user(user_id):
    try:
        oid = ObjectId(user_id)
    except Exception:
        return None
    user_dict = users_collection.find_one({"_id": oid})
    return User(user_dict) if user_dict else None

# ---------------- Dynamic Impact Engine (domain detection + profiling) ----------------
DOMAIN_KEYWORDS = {
    "corporate": ["company", "corporate", "employee", "salary", "wage", "ceo", "manager", "executive", "shareholder", "union", "hr", "workplace", "contractor"],
    "education": ["school", "education", "student", "teacher", "college", "university", "tuition", "scholarship", "curriculum"],
    "environment": ["environment", "climate", "pollution", "plastic", "emission", "carbon", "recycle", "wildlife", "packaging"],
    "society": ["caste", "discrimination", "public", "community", "welfare", "rights", "social", "poverty", "healthcare"],
    "technology": ["ai", "algorithm", "data", "privacy", "surveillance", "software", "app", "platform", "internet", "blockchain", "cybersecurity", "data localization"],
    "military": ["army", "defense", "military", "soldier", "weapon", "security", "navy", "airforce", "conscription"]
}

VALID_LEGAL_DOMAINS = [
    "Civil Law", "Criminal Law", "Constitutional Law", "Corporate Law", 
    "Family Law", "International Law", "Intellectual Property Law", 
    "Labor Law", "Environmental Law", "Other"
]

BASE_PROFILES = {
    "society": ["Educated citizens", "Uneducated citizens", "Rich", "Poor", "Government institutions", "NGOs"],
    "corporate": ["Entry-level employees", "Middle management", "Executives", "Shareholders", "HR department"],
    "environment": ["Manufacturers", "Retailers", "Consumers", "Environmental activists", "Government enforcement agencies"],
    "education": ["Students", "Teachers", "Parents", "School administrators", "Education boards"],
    "technology": ["Users/Consumers", "Developers", "Platform owners", "Regulators", "Privacy advocates"],
    "military": ["Soldiers", "Commanders", "Defense contractors", "Civilians near bases", "Government defense agencies"]
}

POS_WORDS = {"benefit", "advance", "improve", "positive", "support", "protect", "encourage", "reduce", "free", "accessible"}
NEG_WORDS = {"harm", "penalize", "restrict", "burden", "costly", "danger", "risk", "ban", "illegal", "limit"}

SUBGROUP_AUGMENT_RULES = {
    "salary": ["Temporary contractors", "Union representatives"],
    "ceo": ["Board of Directors"],
    "plastic": ["Packaging suppliers"],
    "student": ["Undergraduate students", "Graduate students"],
    "privacy": ["Data brokers", "Security researchers"],
    "army": ["Veterans", "Families of soldiers"],
    "data localization": ["Cloud providers", "International partners"]
}

def normalize_text(text):
    return re.sub(r'\s+', ' ', (text or "").strip().lower())

def detect_domain(law_text):
    txt = normalize_text(law_text)
    domain_scores = {d: 0 for d in DOMAIN_KEYWORDS}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', txt):
                domain_scores[domain] += 1
    try:
        best = max(domain_scores, key=domain_scores.get)
        if domain_scores.get(best, 0) == 0:
            return "society" # Default if no keywords matched
        return best
    except ValueError:
        return "society" # Default if scores dict is empty


def build_dynamic_profile(domain, law_text):
    txt = normalize_text(law_text)
    base = list(BASE_PROFILES.get(domain, BASE_PROFILES["society"]))
    for trigger, extra_groups in SUBGROUP_AUGMENT_RULES.items():
        if re.search(r'\b' + re.escape(trigger) + r'\b', txt):
            for g in extra_groups:
                if g not in base:
                    base.append(g)
    if re.search(r'\bsmall business\b|\bmsme\b|\bstartup\b', txt) and "Small business owners" not in base:
        base.append("Small business owners")
    if re.search(r'\bpoor\b|\bpoverty\b', txt) and "Poor" not in base:
        base.append("Poor")
    return base

def sentiment_score(law_text):
    txt = normalize_text(law_text)
    score = 0
    for w in POS_WORDS:
        if re.search(r'\b' + re.escape(w) + r'\b', txt):
            score += 1
    for w in NEG_WORDS:
        if re.search(r'\b' + re.escape(w) + r'\b', txt):
            score -= 1
    if re.search(r'\b(fin(e|es?|ing)|penal|punish|limit|ban|restrict)\b', txt):
        score -= 1
    score = max(-3, min(3, score))
    return score

def impact_label_from_score(score):
    if score >= 2:
        return "Strong positive"
    elif score == 1:
        return "Positive"
    elif score == 0:
        return "Neutral"
    elif score == -1:
        return "Negative"
    else: # score <= -2
        return "Strong negative"

def generate_group_specific_modifier(group, law_text):
    """
    Creates REAL variations in perspective between groups.
    """
    txt = normalize_text(law_text)
    g = group.lower()
    modifier = 0

    # --- NEW: baseline personality behaviour ---
    personality_bias = {
        "educated": 1,
        "uneducated": -1,
        "rich": 1,
        "poor": -1,
        "student": 1,
        "parent": 0,
        "employee": -1,
        "executive": 1,
        "ngo": -1,
        "government": 1,
        "soldier": 1,
        "activist": -1,
        "consumer": 0
    }

    for p_key, p_val in personality_bias.items():
        if p_key in g:
            modifier += p_val

    # --- If law mentions the group directly → extra relevance ---
    for token in g.split():
        if token and re.search(r'\b' + re.escape(token) + r'\b', txt):
            modifier += 2

    # --- Domain-sensitive reactions ---
    if "penalty" in txt or "fine" in txt:
        if "poor" in g or "uneducated" in g:
            modifier -= 1
        if "rich" in g or "executive" in g:
            modifier += 0.5

    if "tax" in txt or "fee" in txt:
        if "business" in g or "manufacturer" in g:
            modifier -= 1

    if "student" in g and "education" in txt:
        modifier += 2

    return modifier

def make_explanation(group, domain, score, law_text):
    base_explanations = {
        "educated": "This group tends to evaluate laws logically and value long-term benefits.",
        "uneducated": "This group may struggle to understand complex provisions and fear exploitation.",
        "rich": "Higher-income groups focus on economic stability and investment effects.",
        "poor": "Lower-income groups are more affected by penalties, costs, or compliance burdens.",
        "student": "Students react strongly to changes in education access and academic freedom.",
        "employee": "Employees worry about job security, wages, and workplace rights.",
        "executive": "Executives prioritize operational costs, compliance, and business freedom.",
        "ngo": "NGOs react based on social justice, welfare, and ethical impact.",
        "government": "Government bodies evaluate practicality, enforcement, and governance impact.",
        "soldier": "Defense groups consider national security, discipline, and stability.",
        "consumer": "Consumers focus on price, accessibility, and safety of services."
    }

    personal_note = ""
    for key, val in base_explanations.items():
        if key in group.lower():
            personal_note = val
            break

    impact_comment = {
        "Strong positive": "This group benefits greatly from the law.",
        "Positive": "This group experiences mild or moderate benefits.",
        "Neutral": "The group is not significantly affected.",
        "Negative": "The group faces mild disadvantages.",
        "Strong negative": "Severe negative consequences expected."
    }

    impact_label = impact_label_from_score(score)
    return f"{impact_comment[impact_label]} {personal_note}"

@explainability.explainable("dynamic_impact_analysis")
def generate_dynamic_impact_analysis(law_text):
    domain = detect_domain(law_text)
    profile = build_dynamic_profile(domain, law_text)
    base_score = sentiment_score(law_text)
    impacts = {}
    for group in profile:
        modifier = generate_group_specific_modifier(group, law_text)
        group_score = base_score + modifier
        group_score = max(-3, min(3, group_score)) # Clamp score
        impacts[group] = {
            "label": impact_label_from_score(group_score),
            "score": group_score,
            "explanation": make_explanation(group, domain, group_score, law_text)
        }
    return {"domain": domain, "profile": profile, "impacts": impacts}


# ---------------- LLM Helpers ----------------
def summarize_text_llm(text: str):
    if not model:
        print("ℹ️ summarize_text_llm: Using fallback summary (Gemini model not initialized globally).")
        if not text: return ""
        sents = re.split(r'(?<=[.!?])\s+', text.strip())
        summary = sents[0] if sents else ""
        if len(sents) > 1: summary += " " + sents[1]
        return summary[:250] + '...' if len(summary) > 250 else summary
    try:
        print(f"   Attempting summary with model: {model.model_name}")
        prompt = f"Summarize the following legal text in one or two simple, neutral sentences:\n\n---\n\n{text}"
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        response = model.generate_content(prompt, safety_settings=safety_settings)
        if not response.parts:
            feedback = response.prompt_feedback if hasattr(response, 'prompt_feedback') else 'No feedback available'
            print(f"⚠️ Summarization blocked or empty response. Feedback: {feedback}")
            return "Summary could not be generated (content may be sensitive or blocked)."
        return response.text.strip() or "Could not generate a summary."
    except google.api_core.exceptions.NotFound as e:
        print(f"❌ Summarization Error (404 Not Found): {e}. Check model name '{model.model_name}'.")
        return f"Error: Model {model.model_name} not found."
    except google.api_core.exceptions.PermissionDenied as e:
        print(f"❌ Summarization Error (Permission Denied): {e}. Check API key validity.")
        return "Error: API key invalid or lacks permission."
    except google.api_core.exceptions.ResourceExhausted as e:
        print(f"❌ Summarization Error (Rate Limit): {e}. Too many requests.")
        return "Error: API rate limit exceeded. Please wait and try again."
    except Exception as e:
        print(f"❌ Unexpected Summarization error: {e}")
        return "Error during summary generation."


@explainability.explainable("simulate_law_llm")
def simulate_law_llm(law_text: str, country: str = None, legal_domain: str = None):
    if not model:
        print("ℹ️ simulate_law_llm: Using fallback simulation (Gemini model not initialized globally).")
        try:
            dynamic = generate_dynamic_impact_analysis(law_text)
            fallback_base = {
                "positives": ["Promotes general welfare (fallback)."],
                "negatives": ["May face implementation hurdles.", "Potential for unintended side effects (fallback)."],
                "solutions": ["Conduct thorough stakeholder reviews.", "Monitor impact closely post-implementation (fallback)."],
                "impact": dynamic["impacts"],
                "alternative": "Consider refining specific clauses or exploring non-legislative solutions (fallback).",
                "risk_score": 6.5,
                "risk_justification": "Fallback: AI model analysis unavailable. Risk estimated.",
                "_detected_domain": dynamic["domain"],
                "_profile": dynamic["profile"]
            }
            return fallback_base
        except Exception as impact_err:
            print(f"❌ Error during FULL fallback dynamic impact analysis: {impact_err}")
            return { "positives": ["Error generating analysis."], "negatives": ["Error generating analysis."], "solutions": [], "impact": {}, "alternative": "Review input.", "risk_score": 5.0, "risk_justification": "Fallback due to multiple errors.", "_detected_domain": "unknown", "_profile": [] }


    # --- Prompt Engineering ---
    # Explicitly binding the model to the context constraints
    jurisdiction_clause = f"JURISDICTION: {country}" if country else "JURISDICTION: International / General"
    domain_clause = f"LEGAL DOMAIN: {legal_domain}" if legal_domain else "LEGAL DOMAIN: General Legal Reasoning"
    
    context_instruction = (
        "You are an expert AI Legal Analyst acting as a Judge's Assistant.\n"
        f"{jurisdiction_clause}\n"
        f"{domain_clause}\n\n"
        "Your analysis MUST be grounded in the laws, precedents, and legal principles applicable to the specified Jurisdiction and Domain.\n"
        "If the domain is Criminal Law, focus on burden of proof, rights of the accused, and statutory penalties.\n"
        "If the domain is Civil Law, focus on liability, damages, and dispute resolution.\n"
        "If the jurisdiction is specific (e.g., India, USA), cite relevant constitutional articles or major statutes if applicable."
    )

    prompt = f"""
{context_instruction}

TASK: Analyze this proposed law/case text:
\"\"\"{law_text}\"\"\"


Return ONLY valid JSON (no extra text before or after the JSON object, no markdown ```json).
Your response must strictly follow this JSON structure:
{{
  "positives": ["string"],
  "negatives": ["string"],
  "solutions": ["string"],
  "impact": {{}} ,
  "alternative": "string",
  "risk_score": float (0.0-10.0),
  "risk_justification": "string"
}}
Provide concise lists for positives, negatives, and solutions (1-3 items each).
The "impact" field MUST be an empty JSON object {{}}.
Keep alternative and risk_justification brief (1-2 sentences).
"""
    try:
        print(f"   Attempting simulation with model: {model.model_name}")
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        generation_config = genai.types.GenerationConfig(
            temperature=0.3
        )

        response = model.generate_content(
            prompt,
            generation_config=generation_config,
            safety_settings=safety_settings
        )

        result_text = ""
        if response.parts:
            result_text = response.text.strip()
        else:
            feedback = response.prompt_feedback if hasattr(response, 'prompt_feedback') else 'No feedback available'
            block_reason = feedback.block_reason if hasattr(feedback, 'block_reason') else 'Unknown'
            print(f"⚠️ Simulation response blocked or empty. Reason: {block_reason}. Feedback: {feedback}")
            raise ValueError(f"Gemini response blocked or empty (Reason: {block_reason})")

        json_start = result_text.find('{')
        json_end = result_text.rfind('}') + 1

        if json_start != -1 and json_end > json_start:
            json_str = result_text[json_start:json_end]
            try:
                result = json.loads(json_str)
            except json.JSONDecodeError as json_err:
                print(f"❌ JSON Decode Error: {json_err}. Attempting to parse: '{json_str}'")
                raise ValueError("Model returned invalid JSON format") from json_err
        else:
            print(f"❌ Could not find valid JSON object in response: '{result_text}'")
            raise ValueError("Model did not return JSON object")

        expected_keys = {"positives", "negatives", "solutions", "impact", "alternative", "risk_score", "risk_justification"}
        if not isinstance(result, dict) or not expected_keys.issubset(result.keys()):
            print(f"❌ Invalid JSON schema. Expected: {expected_keys}, Got: {result.keys()}")
            raise ValueError("Invalid JSON schema from model")
        if not isinstance(result.get("impact"), dict):
            print(f"❌ 'impact' field is not an object, got: {type(result.get('impact'))}")
            raise ValueError("'impact' field must be an object")

        dynamic = generate_dynamic_impact_analysis(law_text)
        result["impact"] = dynamic["impacts"]
        result["_detected_domain"] = dynamic["domain"]
        result["_profile"] = dynamic["profile"]
        print("✅ Gemini simulation successful, dynamic impact applied.")
        return result

    except google.api_core.exceptions.NotFound as e:
        print(f"❌ Simulation Error (404 Not Found): {e}. Check model name '{model.model_name}'.")
        error_message = f"Error: Model {model.model_name} not found."
    except google.api_core.exceptions.PermissionDenied as e:
        print(f"❌ Simulation Error (Permission Denied): {e}. Check API key validity.")
        error_message = "Error: API key invalid or lacks permission."
    except google.api_core.exceptions.ResourceExhausted as e:
        print(f"❌ Simulation Error (Rate Limit): {e}. Too many requests.")
        error_message = "Error: API rate limit exceeded. Please wait and try again."
    except ValueError as e:
        print(f"❌ Simulation Data Error: {e}")
        error_message = f"Error processing AI response: {e}"
    except Exception as e:
        print(f"❌ Unexpected Simulation error: {e}")
        error_message = "An unexpected error occurred during AI simulation."

    print(f"⚠️ Triggering fallback simulation due to error: {error_message}")
    try:
        dynamic = generate_dynamic_impact_analysis(law_text)
        fallback_base = {
            "positives": ["Review analysis manually (fallback)."],
            "negatives": [f"AI analysis failed: {error_message}", "Potential risks undetermined (fallback)."],
            "solutions": ["Verify input text.", "Check application logs (fallback)."],
            "impact": dynamic["impacts"],
            "alternative": "Consult documentation or try again later (fallback).",
            "risk_score": 5.0,
            "risk_justification": f"Fallback due to error: {error_message}. Risk is estimated.",
            "_detected_domain": dynamic["domain"],
            "_profile": dynamic["profile"]
        }
        return fallback_base
    except Exception as impact_err:
        print(f"❌ Error during FULL fallback dynamic impact analysis: {impact_err}")
        return { "positives": ["Error generating analysis."], "negatives": ["Error generating analysis."], "solutions": [], "impact": {}, "alternative": "Review input.", "risk_score": 5.0, "risk_justification": f"Fallback due to multiple errors ({error_message}).", "_detected_domain": "unknown", "_profile": [] }

# ---------------- Routes: Signup / Login / Logout ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        flash("Please log out before creating a new account.", "warning")
        return redirect(url_for("logout"))

    if request.method == "POST":
        role = request.form.get("role")
        username = request.form.get("username").strip()
        email = request.form.get("email").strip().lower()
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        # ONLY normal users can sign up
        if role != "user":
            flash("Only User accounts can be created here. Admin/Judge/Lawmaker/Simulator accounts must be created by System Administrator.", "danger")
            return redirect(url_for("signup"))

        # Username validations
        if not username or len(username) < 3:
            flash("Username must be at least 3 characters.", "danger")
            return redirect(url_for("signup"))

        if users_collection.find_one({"username": username}):
            flash("Username already exists!", "danger")
            return redirect(url_for("signup"))

        hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

        users_collection.insert_one({
            "role": "user",
            "username": username,
            "password": hashed_pw,
            "email": email,
            "s_id": None,
            "created_at": datetime.now()
        })

        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        selected_role = request.form.get("role", "").lower()
        password = request.form.get("password", "")

        if selected_role == "user":
            username = request.form.get("username", "").strip()
            user = users_collection.find_one({"username": username})

            if not user:
                flash("Username not found.", "danger")
                return render_template("login.html")

            # SMART CHECK: Handles both scrypt and bcrypt automatically
            if verify_password(password, user["password"]):
                login_user(User(user))
                session.update({"username": username, "role": "user"})
                flash("Login successful!", "success")
                return redirect(url_for("simulator"))
            else:
                flash("Incorrect password.", "danger")

        else:
            s_id = request.form.get("s_id", "").strip()
            # Case-insensitive role check if needed, but DB stores lowercase
            user = users_collection.find_one({"s_id": s_id, "role": selected_role})

            if user:
                # FIX: Use bcrypt to verify password (handles bytes/str automatically)
                stored_pw = user.get("password")
                # Ensure stored_pw is bytes for bcrypt
                if isinstance(stored_pw, str):
                    stored_pw = stored_pw.encode('utf-8')

                try:
                    is_valid = bcrypt.checkpw(password.encode('utf-8'), stored_pw)
                except ValueError:
                    # Invalid salt or hash
                    is_valid = False
                except Exception as e:
                    print(f"❌ Error verifying password: {e}")
                    is_valid = False

                if is_valid:
                    login_user(User(user))
                    session.update({"username": user["username"], "role": selected_role})
                    flash(f"Welcome, {user['username']}!", "success")
                    
                    # Redirect based on role
                    dashboards = {
                        "admin": "admin_dashboard",
                        "judge": "judge_dashboard",
                        "lawmaker": "lawmaker_dashboard",
                        "simulator": "simulator"
                    }
                    target = dashboards.get(selected_role, "simulator")
                    print(f"✅ Login successful. Redirecting to {target}...")
                    return redirect(url_for(target))
                else:
                    flash("Invalid System ID or Password.", "danger")
            else:
                 flash("Invalid System ID or Password.", "danger")

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

#------------ PART 2 (start) ----------------
# -------------------- Admin Dashboard helpers & routes --------------------

def generate_random_password(length=10):
    """Generate a secure random password mixing letters, digits, symbols."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    while True:
        pwd = ''.join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.islower() for c in pwd) and any(c.isupper() for c in pwd)
                and any(c.isdigit() for c in pwd) and any(c in "!@#$%^&*()-_=+" for c in pwd)):
            return pwd

def admin_required(fn):
    """Decorator to restrict route to admin role."""
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or getattr(current_user, "role", None) != "admin":
            flash("Access denied. Admins only.", "danger")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

# -------------------- ADMIN DASHBOARD --------------------
@app.route("/admin", methods=["GET"])
@login_required
@admin_required
def admin_dashboard():
    print("🔹 Entered admin_dashboard route")
    """Admin page: create privileged users, list privileged users."""
    try:
        privileged_cursor = users_collection.find({
            "role": {"$in": ["admin", "judge", "lawmaker", "simulator"]}
        })

        privileged_users = []
        print("🔹 Fetching privileged users...")
        for u in privileged_cursor:
            print(f"   Processing user: {u.get('username')}")

            # Timezone handling: Simplified to show stored time (assuming Local)
            c_at = u.get("created_at")
            if isinstance(c_at, datetime):
                c_str = c_at.strftime("%Y-%m-%d %H:%M")
            else:
                c_str = str(c_at)

            privileged_users.append({
                "id": str(u.get("_id")),
                "username": u.get("username"),
                "role": u.get("role"),
                "s_id": u.get("s_id"),
                "email": u.get("email"),
                "created_at": c_str
            })
        print(f"✅ Found {len(privileged_users)} users. Rendering template...")

        return render_template(
            "admin_dashboard.html",
            privileged_users=privileged_users,
            username=current_user.username
        )
    except Exception as e:
        print(f"❌ CRITICAL ERROR IN ADMIN_DASHBOARD: {e}")
        import traceback
        traceback.print_exc()
        return f"CRITICAL ERROR: {e}", 500

@app.route("/admin/explanations", methods=["GET"])
@login_required
@admin_required
def admin_explanations():
    """Expose explainability logs for audit."""
    try:
        import explainability
        if not explainability.recorder:
            return "Explainability Recorder not initialized.", 500
        records = explainability.recorder._load_records()
        return json.dumps(records, indent=2), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        return f"Error: {e}", 500 

# -------------------- CREATE PRIVILEGED USER --------------------
@app.route("/admin/create", methods=["POST"])
@login_required
@admin_required
def admin_create_user():
    """
    Admin creates: admin, judge, lawmaker, simulator.
    Each gets: username + s_id + password (auto/manual)
    """
    role = request.form.get("role")
    username = request.form.get("username", "").strip()
    password_choice = request.form.get("password_choice", "auto")
    manual_password = request.form.get("manual_password", "").strip()
    email = request.form.get("email", "").strip() or None

    if role not in ROLE_PREFIX:
        flash("Invalid role selected.", "danger")
        return redirect(url_for("admin_dashboard"))

    if not username or not re.match(r"^[a-zA-Z0-9_.-]{3,30}$", username):
        flash("Invalid username (3-30 chars, letters/numbers/._-).", "danger")
        return redirect(url_for("admin_dashboard"))

    # Username collision check
    if users_collection.find_one({"username": username}):
        flash("Username already exists.", "danger")
        return redirect(url_for("admin_dashboard"))

    # Password
    if password_choice == "manual":
        if len(manual_password) < 6:
            flash("Manual password too short (min 6).", "danger")
            return redirect(url_for("admin_dashboard"))
        password_plain = manual_password
    else:
        password_plain = generate_random_password(12)

    # Generate system ID
    s_id = generate_system_id(role)
    hashed_pw = bcrypt.hashpw(password_plain.encode(), bcrypt.gensalt())

    user_doc = {
        "username": username,
        "password": hashed_pw,
        "role": role,
        "s_id": s_id,
        "email": email,
        "created_at": datetime.now()
    }

    try:
        users_collection.insert_one(user_doc)
    except Exception as e:
        print(f"❌ Error inserting privileged user: {e}")
        flash("Database error while creating privileged user.", "danger")
        return redirect(url_for("admin_dashboard"))

    flash(f"Created {role} — username: {username}, system ID: {s_id}", "success")
    flash(f"Temporary password: {password_plain}", "info")  # show password once
    return redirect(url_for("admin_dashboard"))

# -------------------- DELETE PRIVILEGED USER --------------------
@app.route("/admin/delete/<user_id>", methods=["POST"])
@login_required
@admin_required
def admin_delete_user(user_id):
    try:
        oid = ObjectId(user_id)
    except:
        flash("Invalid user ID.", "danger")
        return redirect(url_for("admin_dashboard"))

    doc = users_collection.find_one({"_id": oid})
    if not doc:
        flash("User not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    if doc.get("role") == "user":
        flash("Cannot delete normal user from this admin panel.", "danger")
        return redirect(url_for("admin_dashboard"))

    users_collection.delete_one({"_id": oid})
    flash(f"Deleted privileged user {doc.get('username')} ({doc.get('s_id')}).", "success")
    return redirect(url_for("admin_dashboard"))

# -------------------- LAWMAKER ROUTE --------------------
@app.route("/lawmaker", methods=["GET", "POST"])
@login_required
def lawmaker_dashboard():
    # Only lawmakers and admins can access this
    if current_user.role not in ["lawmaker", "admin"]:
        flash("Access denied. Lawmakers only.", "danger")
        return redirect(url_for("simulator"))

    summary = None
    positives = None
    negatives = None
    solutions = None
    risk_score_display = None
    recommendation = None

    # When the lawmaker submits draft law text
    if request.method == "POST":
        law_text = request.form.get("law_text", "").strip()

        if not law_text:
            flash("Please enter law content to analyze.", "danger")
            return render_template("lawmaker_dashboard.html", username=current_user.username)

        # --------------------
        # AI SUMMARY
        # --------------------
        summary = summarize_text_llm(law_text)

        # --------------------
        # AI FULL ANALYSIS
        # --------------------
        result = simulate_law_llm(law_text)

        # Extract lists
        positives = ", ".join(result.get("positives", []))
        negatives = ", ".join(result.get("negatives", []))
        solutions = ", ".join(result.get("solutions", []))

        # --------------------
        # RISK SCORE
        # --------------------
        risk = result.get("risk_score", 6.5)
        try:
            risk = float(risk)
            risk = max(0.0, min(10.0, risk))  # ensure 0–10
        except:
            risk = 6.5
        risk_score_display = round(risk, 1)

        # --------------------
        # RECOMMENDATION ENGINE
        # --------------------
        if risk_score_display <= 3.5:
            recommendation = "This law draft is LOW RISK and likely safe to submit. Proceed confidently. ✅"
        elif 3.5 < risk_score_display <= 6.5:
            recommendation = "This draft is MODERATE RISK. Consider applying the suggested solutions before submitting. ⚠️"
        else:
            recommendation = "This draft is HIGH RISK and NOT advisable to submit. Significant revision is needed. ❌"

        # --------------------
        # RENDER WITH RESULT
        # --------------------
        return render_template(
            "lawmaker_dashboard.html",
            username=current_user.username,
            summary=summary,
            positives=positives,
            negatives=negatives,
            solutions=solutions,
            risk_score=risk_score_display,
            recommendation=recommendation
        )

    # GET request → show empty dashboard
    return render_template("lawmaker_dashboard.html", username=current_user.username)

# ---------------- Simulator Route ----------------
@app.route("/judge", methods=["GET", "POST"])
@login_required
def judge_dashboard():
    if current_user.role != "judge":
        return redirect(url_for("simulator"))

    summary = None
    verdict = None
    verdict_reason = None
    risk_score_display = None
    result = None


    if request.method == "POST":
        case_text = request.form.get("case_text", "").strip()
        country_input = request.form.get("country", "").strip()
        domain_input = request.form.get("domain", "").strip()

        # --- Validation & Defaults ---
        # 1. Country: Defaults to "India" if empty (as mostly local usage), but we allow explicit "None" if needed.
        # Here we just treat empty as None for the function, letting the Prompt defaults handle it, 
        # OR we can force "India" if we want to be opinionated. 
        # Plan says: Default "India" in UI, but if user clears it? Let's use "India" as safe default for this Simulator context.
        country = country_input if country_input else "India"

        # 2. Domain: Whitelist validation
        if domain_input not in VALID_LEGAL_DOMAINS:
            legal_domain = "General" # Fallback
        else:
            legal_domain = domain_input
            
        if not case_text:
             flash("Please enter case details.", "warning")
             # RENDER with preserved state even on error
             return render_template("judge_dashboard.html", username=current_user.username, country=country, legal_domain=legal_domain)

        # --- Use real simulation functions ---
        summary = summarize_text_llm(case_text)
        result = simulate_law_llm(case_text, country=country, legal_domain=legal_domain)

        # Risk Score
        risk_score_display = float(result.get("risk_score", 5))

        # ---- Verdict Logic ----
        if risk_score_display <= 3.5:
            verdict = "APPROVED"
            verdict_reason = (
                "The proposal carries minimal risk. AI found no major legal, "
                "ethical, or social harm. Safe to implement."
            )

        elif risk_score_display <= 6.5:
            verdict = "NEEDS REVISION"
            verdict_reason = (
                "The proposal shows moderate risks. AI detected ambiguous wording "
                "or potential negative consequences. Revise before approval."
            )

        else:
            verdict = "REJECTED"
            verdict_reason = (
                "The proposal carries high risk. AI detected violations of rights, "
                "ethical concerns, or harmful societal impact. Implementation not advised."
            )

    # Render Page with preserved state
    return render_template(
        "judge_dashboard.html",
        username=current_user.username,
        summary=summary,
        verdict=verdict,
        verdict_reason=verdict_reason,
        result=result,
        risk_score=risk_score_display,
        country=request.form.get("country", "India"), # Default for first load is India
        legal_domain=request.form.get("domain", "")
    )

# ---------------- SIMULATOR DASHBOARD (Normal User) ----------------
@app.route("/simulator", methods=["GET", "POST"])
@login_required
def simulator():
    # Only normal users and simulator-role users can access
    if current_user.role not in ["user", "simulator", "admin", "lawmaker", "judge"]:
        flash("Access denied. Only Users/Simulators can access the AI Simulator.", "danger")
        return redirect(url_for("login"))

    summary = None
    result = None
    risk_score_display = None
    recommendation = None
    history = []
    law_text = ""

    clev_blocked = False
    clev_data = None
    clev_status_tag = None

    if request.method == "POST":
        law_text = request.form.get("law_text", "").strip()
        country_input = request.form.get("country", "").strip()

        # Step 1: Country Validation (Mandatory as per request)
        if not country_input:
            country_input = "India" # Default to India
        
        # Step 2: CLEV (Constitutional Law Existence Validator)
        blocked, match_data, status_tag = validate_law_existence(law_text)
        
        clev_blocked = blocked
        clev_data = match_data
        clev_status_tag = status_tag

        if not law_text:
            flash("Please enter the law text to simulate.", "warning")
            return render_template("simulator.html", username=current_user.username)

        # Logic Branch: Block vs Allow
        if clev_blocked:
            # STOP simulation. Show validation error only.
            summary = summarize_text_llm(law_text) # Still show summary of input
            # No result, No history save (optional, but keeps history clean)
        else:
            # Proceed with simulation
            summary = summarize_text_llm(law_text)
            result = simulate_law_llm(law_text, country=country_input)

            risk = float(result.get("risk_score", 6.5))
            risk_score_display = round(max(0.0, min(10.0, risk)), 1)

            # Recommendation
            if risk_score_display <= 3.5:
                recommendation = "SAFE — This proposal is low risk. Good to proceed. ✅"
            elif risk_score_display <= 6.5:
                recommendation = "MODERATE — Consider improvements before submission. ⚠️"
            else:
                recommendation = "HIGH RISK — Not recommended for implementation. ❌"

            # 📌 SAVE to history
            history_collection.insert_one({
                "user_id": current_user.id,
                "timestamp": datetime.now(),
                "input_text": law_text,
                "risk_score": risk_score_display,
                "clev_status": status_tag
            })

    # 📌 FETCH last 10 history items for the logged-in user
    history_cursor = history_collection.find({"user_id": current_user.id}).sort("timestamp", -1).limit(10)
    for item in history_cursor:
        history.append(item)

    return render_template(
        "simulator.html",
        username=current_user.username,
        summary=summary,
        result=result,
        risk_score=risk_score_display,
        recommendation_message=recommendation,
        history=history,
        original_text=law_text, # Preserve input
        clev_blocked=clev_blocked,
        clev_data=clev_data,
        clev_status_tag=clev_status_tag,
        country_selection=request.form.get("country", "India")
    )

# ---------------- Session Timeout ----------------
SESSION_TIMEOUT_MINUTES = 30

@app.before_request
def check_session_timeout():
    if (current_user.is_authenticated and
            request.endpoint not in ['static', 'login', 'signup', None]):
        now = datetime.now()
        last_activity_iso = session.get("last_activity")

        if last_activity_iso:
            try:
                last_activity_dt = datetime.fromisoformat(last_activity_iso)
                if last_activity_dt.tzinfo is not None:
                     last_activity_dt = last_activity_dt.replace(tzinfo=None)

                if now - last_activity_dt > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                    print(f"ℹ️ User '{current_user.username}' timed out due to inactivity.")
                    logout_user()
                    session.clear()
                    flash("You have been logged out due to inactivity.", "warning")
                    return redirect(url_for("login"))
            except ValueError:
                print("⚠️ Invalid 'last_activity' format in session, resetting.")
                session["last_activity"] = now.isoformat()
            except Exception as e:
                print(f"❌ Error during session timeout check: {e}")
                session["last_activity"] = now.isoformat()

        session["last_activity"] = now.isoformat()
        session.modified = True


# ---------------- Home Route ----------------
@app.route("/")
def home():
    if not current_user.is_authenticated:
        return redirect(url_for("login"))
    return redirect(url_for("simulator"))


# ---------------- FLUENT UI: Design Tokens + CSS/JS Routes ----------------
# Design tokens for AI Fluent (Design 4)
DESIGN_TOKENS = {
    "app_name": "AI Future Law Simulator",
    "font_stack": "'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial",
    "bg": "#F5F7FA",
    "panel": "#FFFFFF",
    "border": "#E6E9EF",
    "text_primary": "#1E293B",
    "text_secondary": "#475569",
    "accent_blue_start": "#4F8DFD",
    "accent_blue_end": "#3B6FF7",
    "accent_teal": "#14B8A6",
    "shadow": "rgba(0,0,0,0.04)",
    "radius_card": "12px",
    "radius_button": "8px"
}

@app.context_processor
def inject_design_tokens():
    # Provides tokens to Jinja templates if desired
    return {
        "APP_NAME": DESIGN_TOKENS["app_name"],
        "DESIGN_TOKENS": DESIGN_TOKENS
    }

# CSS generator endpoint — returns the design-system CSS (so you don't have to ship a separate static file)
@app.route("/design-system.css")
def design_css():
    css = f"""
/* AI Fluent Design System - autogenerated by server */
:root {{
  --bg: {DESIGN_TOKENS['bg']};
  --panel: {DESIGN_TOKENS['panel']};
  --border: {DESIGN_TOKENS['border']};
  --text-primary: {DESIGN_TOKENS['text_primary']};
  --text-secondary: {DESIGN_TOKENS['text_secondary']};
  --accent-blue-start: {DESIGN_TOKENS['accent_blue_start']};
  --accent-blue-end: {DESIGN_TOKENS['accent_blue_end']};
  --accent-teal: {DESIGN_TOKENS['accent_teal']};
  --shadow: {DESIGN_TOKENS['shadow']};
  --radius-card: {DESIGN_TOKENS['radius_card']};
  --radius-button: {DESIGN_TOKENS['radius_button']};
  --font-stack: {DESIGN_TOKENS['font_stack']};
}}

/* Base */
html,body {{
  height:100%;
  margin:0;
  background:var(--bg);
  color:var(--text-primary);
  font-family: var(--font-stack);
  -webkit-font-smoothing:antialiased;
  -moz-osx-font-smoothing:grayscale;
}}

.container {{
  max-width:1200px;
  margin:24px auto;
  padding:16px;
}}

/* Fluent panels / cards */
.card {{
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: 0 6px 18px var(--shadow);
  padding:16px;
  transition: transform 180ms ease, box-shadow 180ms ease;
}}

.card:hover {{
  transform: translateY(-4px);
  box-shadow: 0 12px 30px rgba(0,0,0,0.06);
}}

/* Headings */
.h1 {{ font-size:20px; margin:0 0 8px 0; font-weight:600; color:var(--text-primary); }}
.h2 {{ font-size:16px; margin:0 0 6px 0; font-weight:600; color:var(--text-primary); }}
.p-muted {{ color:var(--text-secondary); font-size:14px; }}

/* Buttons */
.btn {{
  display:inline-block;
  border-radius: var(--radius-button);
  padding:10px 14px;
  font-weight:600;
  border: none;
  cursor: pointer;
  transition: transform 150ms ease, box-shadow 150ms ease;
}}

.btn-primary {{
  background: linear-gradient(90deg, var(--accent-blue-start), var(--accent-blue-end));
  color:white;
  box-shadow: 0 6px 18px rgba(59,111,247,0.18);
}}

.btn-primary:hover {{ transform: translateY(-2px); }}

.btn-ghost {{
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-primary);
}}

/* Topbar */
.topbar {{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:12px;
  padding:12px 20px;
  background: linear-gradient(180deg, rgba(255,255,255,0.9), rgba(246,248,252,0.9));
  border-bottom: 1px solid var(--border);
  backdrop-filter: blur(6px);
}}

.search {{
  min-width:320px;
  max-width:640px;
  display:flex;
  align-items:center;
  gap:8px;
  background:var(--panel);
  padding:8px 12px;
  border-radius:10px;
  border: 1px solid var(--border);
  box-shadow: none;
}}

/* Sidebar (basic style) */
.sidebar {{
  width:220px;
  background:transparent;
  padding:12px;
}}
.sidebar .nav-item {{
  display:flex;
  align-items:center;
  gap:10px;
  padding:10px;
  border-radius:8px;
  color:var(--text-primary);
}}
.sidebar .nav-item.active {{
  background: linear-gradient(90deg, rgba(79,141,253,0.12), rgba(59,111,247,0.08));
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.6);
}}

/* Fluent timeline */
.timeline {{
  display:flex;
  gap:12px;
  align-items:center;
  padding:12px 0;
}}
.timeline .node {{
  width:12px;
  height:12px;
  border-radius:999px;
  background: linear-gradient(180deg, var(--accent-blue-start), var(--accent-blue-end));
  box-shadow: 0 4px 12px rgba(59,111,247,0.18);
}}

/* Small utilities */
.kv {{
  display:flex;
  gap:8px;
  align-items:center;
}}
.badge {{
  padding:6px 8px;
  border-radius:999px;
  font-weight:600;
  font-size:13px;
  background: linear-gradient(90deg, rgba(20,184,166,0.12), rgba(20,184,166,0.06));
  color: var(--accent_teal);
}}

/* Responsive */
@media (max-width:900px) {{
  .container {{ padding:10px; }}
  .sidebar {{ display:none; }}
}}

"""
    return Response(css, mimetype="text/css")


# Minimal UI JS for small interactions
@app.route("/ui-assets.js")
def ui_assets_js():
    js = """
// Minimal UI helper — sidebar toggle + small helpers
document.addEventListener('DOMContentLoaded', function(){
  // sidebar toggle if present
  const toggleBtn = document.querySelector('[data-sidebar-toggle]');
  const sidebar = document.querySelector('.sidebar');
  if(toggleBtn && sidebar){
    toggleBtn.addEventListener('click', function(){
      sidebar.style.display = sidebar.style.display === 'none' ? '' : 'none';
    });
  }

  // small auto-focus for primary textareas
  const autoFocus = document.querySelector('[data-autofocus]');
  if(autoFocus) autoFocus.focus();
});
"""
    return Response(js, mimetype='application/javascript')

if __name__ == "__main__":
    import threading, webbrowser, time

    SERVER_PORT = 5000
    SERVER_HOST = "127.0.0.1"
    SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

    # Auto-open browser when server starts
    def open_browser():
        time.sleep(2)
        webbrowser.open(f"{SERVER_URL}/login", new=2)

    # Start browser thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Run Flask app (debug enabled for troubleshooting)
    app.run(
        host=SERVER_HOST,
        port=SERVER_PORT,
        debug=True,
        use_reloader=False
    )
