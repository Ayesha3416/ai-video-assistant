import json
import os
import re
import hashlib
import secrets

from config.paths import DATA_DIR, USERS_JSON

USERS_FILE = str(USERS_JSON)
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _ensure_users_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)


def _load_users() -> dict:
    _ensure_users_file()
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_users(users: dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def register_user(email: str, password: str, display_name: str = "") -> tuple[bool, str]:
    email = email.strip().lower()
    display_name = display_name.strip()
    if not email or not password:
        return False, "Email and password cannot be empty."
    if not display_name:
        return False, "Please tell us what to call you."
    if not EMAIL_REGEX.match(email):
        return False, "Please enter a valid email address."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    users = _load_users()
    if email in users:
        return False, "An account with this email already exists."
    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)
    users[email] = {
        "salt": salt,
        "password_hash": password_hash,
        "display_name": display_name,
    }
    _save_users(users)
    return True, "Account created successfully!"


def verify_user(email: str, password: str) -> tuple[bool, str]:
    email = email.strip().lower()
    users = _load_users()

    if email not in users:
        return False, "No account found with that email."

    record = users[email]
    expected_hash = _hash_password(password, record["salt"])

    if expected_hash == record["password_hash"]:
        return True, "Login successful."
    return False, "Incorrect password."

def get_display_name(email: str) -> str:
    email = email.strip().lower()
    users = _load_users()
    record = users.get(email, {})
    return record.get("display_name") or email.split("@")[0]