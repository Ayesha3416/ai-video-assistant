"""User auth, now backed by the SQLite DB (db/models.py) instead of
data/users.json. Public API is unchanged on purpose -- register_user(),
verify_user(), get_display_name() keep the exact same signatures/return
shapes -- so ui/auth_pages.py, ui/navbar.py, ui/sidebar.py needed no changes
at all for this switch.

Step 7a already migrated existing accounts into the users table; this file
now reads/writes that table instead of the old JSON, using the same
bcrypt-with-legacy-fallback logic Step 5 established (see db/models.py
User docstring for why bcrypt_hash / legacy_salt / legacy_password_hash all
exist side by side).
"""
import hashlib
import re

import bcrypt

from config import settings
from db.session import get_db
from db.models import User

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _hash_password_legacy(password: str, salt: str) -> str:
    """Old scheme (salted SHA-256). Only used to verify accounts that haven't
    logged in since the bcrypt switch -- never used for new hashes."""
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def _hash_password_bcrypt(password: str) -> str:
    hashed = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    )
    return hashed.decode("utf-8")


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

    with get_db() as db:
        if db.query(User).filter_by(email=email).first():
            return False, "An account with this email already exists."

        user = User(
            email=email,
            display_name=display_name,
            bcrypt_hash=_hash_password_bcrypt(password),
        )
        db.add(user)
        db.commit()

    return True, "Account created successfully!"


def _sync_admin_role(user: User) -> None:
    """Keep role in sync with settings.ADMIN_EMAILS on every login -- so
    granting/revoking admin access is just editing .env and restarting, no
    script or manual DB edit needed. Doesn't touch anything else about the
    account."""
    should_be_admin = user.email in settings.admin_emails
    if should_be_admin and user.role != "admin":
        user.role = "admin"
    elif not should_be_admin and user.role == "admin":
        user.role = "user"


def verify_user(email: str, password: str) -> tuple[bool, str]:
    email = email.strip().lower()

    with get_db() as db:
        user = db.query(User).filter_by(email=email).first()
        if not user:
            return False, "No account found with that email."

        if user.bcrypt_hash:
            ok = bcrypt.checkpw(
                password.encode("utf-8"), user.bcrypt_hash.encode("utf-8")
            )
            if not ok:
                return False, "Incorrect password."
            _sync_admin_role(user)
            db.commit()
            return True, "Login successful."

        # Legacy salted-SHA-256 account: verify the old way, then transparently
        # upgrade to bcrypt on successful login (same as Step 5's JSON version).
        expected_hash = _hash_password_legacy(password, user.legacy_salt or "")
        if expected_hash != user.legacy_password_hash:
            return False, "Incorrect password."

        user.bcrypt_hash = _hash_password_bcrypt(password)
        user.legacy_salt = None
        user.legacy_password_hash = None
        _sync_admin_role(user)
        db.commit()

    return True, "Login successful."


def get_display_name(email: str) -> str:
    email = email.strip().lower()
    with get_db() as db:
        user = db.query(User).filter_by(email=email).first()
        if user and user.display_name:
            return user.display_name
    return email.split("@")[0]


def is_admin(email: str) -> bool:
    email = email.strip().lower()
    with get_db() as db:
        user = db.query(User).filter_by(email=email).first()
        return bool(user and user.role == "admin")


def update_display_name(email: str, new_name: str) -> tuple[bool, str]:
    email = email.strip().lower()
    new_name = new_name.strip()
    if not new_name:
        return False, "Display name can't be empty."
    if len(new_name) > 100:
        return False, "Display name is too long (max 100 characters)."

    with get_db() as db:
        user = db.query(User).filter_by(email=email).first()
        if not user:
            return False, "Account not found."
        user.display_name = new_name
        db.commit()

    return True, "Display name updated."


def change_password(email: str, current_password: str, new_password: str) -> tuple[bool, str]:
    email = email.strip().lower()
    if len(new_password) < 8:
        return False, "New password must be at least 8 characters."

    with get_db() as db:
        user = db.query(User).filter_by(email=email).first()
        if not user:
            return False, "Account not found."

        # Verify the CURRENT password first, same bcrypt-or-legacy check
        # verify_user() uses, so this can't be used to overwrite a password
        # without proving you know the existing one.
        if user.bcrypt_hash:
            ok = bcrypt.checkpw(
                current_password.encode("utf-8"), user.bcrypt_hash.encode("utf-8")
            )
        else:
            ok = _hash_password_legacy(
                current_password, user.legacy_salt or ""
            ) == user.legacy_password_hash

        if not ok:
            return False, "Current password is incorrect."

        user.bcrypt_hash = _hash_password_bcrypt(new_password)
        user.legacy_salt = None
        user.legacy_password_hash = None
        db.commit()

    return True, "Password changed successfully."
