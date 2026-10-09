"""
Security configuration and validation helpers for Law Simulator.
"""

import os
import re
import secrets
import sys
from typing import Dict, Optional, Tuple


def load_config_from_env() -> Dict[str, object]:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    return {
        "GENAI_KEY": os.getenv("GENAI_KEY", "").strip(),
        "MONGO_URI": os.getenv("MONGO_URI", "").strip(),
        "FLASK_SECRET_KEY": os.getenv("FLASK_SECRET_KEY", "").strip(),
        "FLASK_ENV": os.getenv("FLASK_ENV", "development"),
        "FLASK_DEBUG": os.getenv("FLASK_DEBUG", "false").lower() in {"true", "1", "yes"},
        "SERVER_HOST": os.getenv("SERVER_HOST", "127.0.0.1"),
        "SERVER_PORT": int(os.getenv("SERVER_PORT", "5000")),
        "SESSION_TIMEOUT_MINUTES": int(os.getenv("SESSION_TIMEOUT_MINUTES", "30")),
        "MAX_LAW_TEXT_LENGTH": int(os.getenv("MAX_LAW_TEXT_LENGTH", "10000")),
        "PASSWORD_MIN_LENGTH": int(os.getenv("PASSWORD_MIN_LENGTH", "12")),
        "PASSWORD_REQUIRE_UPPERCASE": os.getenv("PASSWORD_REQUIRE_UPPERCASE", "true").lower() in {"true", "1", "yes"},
        "PASSWORD_REQUIRE_NUMBERS": os.getenv("PASSWORD_REQUIRE_NUMBERS", "true").lower() in {"true", "1", "yes"},
        "PASSWORD_REQUIRE_SYMBOLS": os.getenv("PASSWORD_REQUIRE_SYMBOLS", "true").lower() in {"true", "1", "yes"},
    }


def validate_config(config: Dict[str, object]) -> Tuple[bool, Optional[str]]:
    for key in ("GENAI_KEY", "MONGO_URI", "FLASK_SECRET_KEY"):
        value = config.get(key)
        if not value or not str(value).strip():
            return False, f"❌ CRITICAL: {key} must be set in environment variables or .env file"

    secret = str(config.get("FLASK_SECRET_KEY", ""))
    if len(secret) < 32:
        return False, "❌ CRITICAL: FLASK_SECRET_KEY must be at least 32 characters long"

    port = int(config.get("SERVER_PORT", 5000))
    if not (1 <= port <= 65535):
        return False, f"❌ Invalid SERVER_PORT: {port}. Must be between 1 and 65535"

    timeout = int(config.get("SESSION_TIMEOUT_MINUTES", 30))
    if timeout < 5:
        return False, "❌ SESSION_TIMEOUT_MINUTES must be at least 5 minutes"

    max_len = int(config.get("MAX_LAW_TEXT_LENGTH", 10000))
    if max_len < 100 or max_len > 1000000:
        return False, "❌ MAX_LAW_TEXT_LENGTH must be between 100 and 1,000,000"

    pwd_min = int(config.get("PASSWORD_MIN_LENGTH", 12))
    if pwd_min < 8 or pwd_min > 128:
        return False, "❌ PASSWORD_MIN_LENGTH must be between 8 and 128"

    return True, None


def validate_password(password: str, config: Optional[Dict[str, object]] = None) -> Tuple[bool, Optional[str]]:
    if not password:
        return False, "Password cannot be empty"

    cfg = config or {}
    min_length = int(cfg.get("PASSWORD_MIN_LENGTH", 12))
    if len(password) < min_length:
        return False, f"Password must be at least {min_length} characters long"

    if len(password) > 128:
        return False, "Password must be no more than 128 characters long"

    if cfg.get("PASSWORD_REQUIRE_UPPERCASE", True) and not any(ch.isupper() for ch in password):
        return False, "Password must contain at least one uppercase letter"

    if cfg.get("PASSWORD_REQUIRE_NUMBERS", True) and not any(ch.isdigit() for ch in password):
        return False, "Password must contain at least one number"

    if cfg.get("PASSWORD_REQUIRE_SYMBOLS", True) and not any(not ch.isalnum() for ch in password):
        return False, "Password must contain at least one special character"

    return True, None


def validate_username(username: str) -> Tuple[bool, Optional[str]]:
    if not username or not isinstance(username, str):
        return False, "Username cannot be empty"
    username = username.strip()
    if len(username) < 3:
        return False, "Username must be at least 3 characters long"
    if len(username) > 30:
        return False, "Username must be no more than 30 characters long"
    if not re.match(r"^[a-zA-Z0-9_.-]{3,30}$", username):
        return False, "Username can only contain letters, numbers, dots, dashes, and underscores"
    return True, None


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    if not email or not isinstance(email, str):
        return False, "Email cannot be empty"
    email = email.strip().lower()
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        return False, "Invalid email format"
    if len(email) > 254:
        return False, "Email is too long"
    return True, None


def validate_law_text(text: str, max_length: int = 10000) -> Tuple[bool, Optional[str]]:
    if not text or not isinstance(text, str):
        return False, "Law text cannot be empty"
    text = text.strip()
    if len(text) < 10:
        return False, "Law text must be at least 10 characters long"
    if len(text) > max_length:
        return False, f"Law text exceeds maximum length of {max_length} characters"
    return True, None


def sanitize_html(text: str) -> str:
    import html
    if not text:
        return ""
    cleaned = html.escape(str(text))
    cleaned = re.sub(r"javascript:", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"on\w+\s*=", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<script.*?</script>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    return cleaned


def generate_secure_password(length: int = 16) -> str:
    if length < 12:
        length = 12
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def load_and_validate_config() -> Dict[str, object]:
    config = load_config_from_env()
    is_valid, error = validate_config(config)
    if not is_valid:
        print(error)
        sys.exit(1)
    return config


if __name__ == "__main__":
    cfg = load_and_validate_config()
    print("Security config validation passed.")
    print(cfg)
