"""
auth.py
-------
Session-based authentication + self-register users + owner-created admins.

Roles: owner > admin > user

Login flow:
- Owner:   username + password + master_key
- Admin:   username + password + key (owner created admin credentials)
- User:    username + password + key
           → if new user, key binds and account created (self-register)
           → if existing, key must match what was bound
"""
from datetime import datetime, timezone, timedelta
from functools import wraps
import hashlib
import secrets

from flask import session as flask_session, jsonify

from config import (
    SESSION_TIMEOUT_MINUTES,
    API_KEY_PREFIX,
    ADMIN_KEY_PREFIX,        # 🔥 NEW
    LIKE_KEY_PREFIX,
)
from db import accounts_col, api_keys_col, like_keys_col
from subscriptionAPI import bind_api_key_to_user
from subscription import bind_like_key_to_user


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


# ============================================================
# INTERNAL — KEY VERIFY / BIND FOR EXISTING USER
# ============================================================
def _verify_or_bind_key(name: str, key: str) -> dict:
    if key.startswith(API_KEY_PREFIX) or key.startswith(ADMIN_KEY_PREFIX):   # 🔥 FF-AD
        key_doc = api_keys_col.find_one({"key": key})
        bind_func = bind_api_key_to_user
        key_field = "assigned_api_key"
    elif key.startswith(LIKE_KEY_PREFIX):
        key_doc = like_keys_col.find_one({"key": key})
        bind_func = bind_like_key_to_user
        key_field = "assigned_like_key"
    else:
        return {"ok": False, "reason": "invalid_key_format"}

    if not key_doc:
        return {"ok": False, "reason": "invalid_key"}

    expires = key_doc.get("expires_at")
    if expires and expires < _now():
        return {"ok": False, "reason": "expired"}

    assigned = key_doc.get("assigned_to")
    if assigned and assigned != name:
        return {"ok": False, "reason": "already_assigned", "assigned_to": assigned}

    if not assigned:
        result = bind_func(key, name)
        if not result.get("ok"):
            return result

    return {"ok": True}


# ============================================================
# LOGIN / SELF-REGISTER
# ============================================================
def authenticate(name: str, password: str, key: str | None = None,
                 like_key: str | None = None) -> dict:
    """
    Login flow:
    - Owner: verify password + master_key
    - Admin: verify password + assigned key
    - User: if exists → verify password + key matches
            if new → create user + bind key
    """
    user = accounts_col.find_one({"name": name})

    # ---------------- EXISTING USER ----------------
    if user:
        if not verify_password(password, user.get("password_hash", "")):
            return {"ok": False, "reason": "invalid_credentials"}

        if user.get("status") != "active":
            return {"ok": False, "reason": "account_suspended"}

        role = user.get("role")

        # ----- OWNER -----
        if role == "owner":
            if not key or key != user.get("master_key"):
                return {"ok": False, "reason": "invalid_master_key"}
            return {"ok": True, "user": user}

        # ----- ADMIN / USER -----
        if not key:
            return {"ok": False, "reason": "key_required"}

        result = _verify_or_bind_key(name, key)
        if not result.get("ok"):
            return result

        user = accounts_col.find_one({"name": name})   # re-fetch
        return {"ok": True, "user": user}

    # ---------------- NEW USER (SELF-REGISTER) ----------------
    if not key:
        return {"ok": False, "reason": "key_required_for_new_account"}

    if not password or len(password) < 4:
        return {"ok": False, "reason": "password_too_short"}

    # Determine key type
    if key.startswith(API_KEY_PREFIX) or key.startswith(ADMIN_KEY_PREFIX):
        key_doc = api_keys_col.find_one({"key": key})
        bind_func = bind_api_key_to_user
        key_field = "assigned_api_key"
    elif key.startswith(LIKE_KEY_PREFIX):
        key_doc = like_keys_col.find_one({"key": key})
        bind_func = bind_like_key_to_user
        key_field = "assigned_like_key"
    else:
        return {"ok": False, "reason": "invalid_key_format"}

    if not key_doc:
        return {"ok": False, "reason": "invalid_key"}

    expires = key_doc.get("expires_at")
    if expires and expires < _now():
        return {"ok": False, "reason": "expired"}

    if key_doc.get("assigned_to"):
        return {
            "ok": False,
            "reason": "already_assigned",
            "assigned_to": key_doc["assigned_to"],
        }

    # Create user
    try:
        accounts_col.insert_one({
            "name": name,
            "password_hash": hash_password(password),
            "role": "user",
            "master_key": None,
            "assigned_api_key": None,
            "assigned_like_key": None,
            "session_token": None,
            "status": "active",
            "created_at": _now(),
            "created_by": "self-register",
        })
    except Exception as e:
        return {"ok": False, "reason": f"create_failed: {e}"}

    # Bind key
    result = bind_func(key, name)
    if not result.get("ok"):
        accounts_col.delete_one({"name": name})
        return result

    user = accounts_col.find_one({"name": name})
    return {"ok": True, "user": user, "new_account": True}


# ============================================================
# SESSION
# ============================================================
def create_session(username: str) -> str:
    token = secrets.token_urlsafe(32)
    expires = _now() + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    accounts_col.update_one(
        {"name": username},
        {"$set": {"session_token": token, "session_expires": expires}},
    )
    return token


def get_session_user(token: str | None):
    if not token:
        return None
    user = accounts_col.find_one({"session_token": token})
    if not user:
        return None
    exp = user.get("session_expires")
    if exp and exp < _now():
        accounts_col.update_one(
            {"name": user["name"]},
            {"$unset": {"session_token": "", "session_expires": ""}},
        )
        return None
    return user


def destroy_session(token: str | None):
    if not token:
        return
    accounts_col.update_one(
        {"session_token": token},
        {"$unset": {"session_token": "", "session_expires": ""}},
    )


def current_user():
    return get_session_user(flask_session.get("token"))


# ============================================================
# DECORATORS
# ============================================================
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user, err = validate_session_realtime()
        if err:
            code, status = err
            return jsonify({"error": code}), status
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user, err = validate_session_realtime()
        if err:
            code, status = err
            return jsonify({"error": code}), status
        if user.get("role") not in ("admin", "owner"):
            return jsonify({"error": "forbidden"}), 403
        return f(*args, **kwargs)
    return wrapper


def owner_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user, err = validate_session_realtime()
        if err:
            code, status = err
            return jsonify({"error": code}), status
        if user.get("role") != "owner":
            return jsonify({"error": "forbidden"}), 403
        return f(*args, **kwargs)
    return wrapper


# ============================================================
# ADMIN CREATION (owner only)
# ============================================================
def create_admin(name: str, password: str, created_by: str,
                 key: str | None = None) -> dict:
    """
    Owner-only: create admin account.
    - If key provided → bind it (must exist + be unbound)
    - If key empty → admin can bind later at login
    """
    from config import API_KEY_PREFIX, LIKE_KEY_PREFIX

    if not name or not password:
        return {"ok": False, "reason": "missing_fields"}

    if len(password) < 4:
        return {"ok": False, "reason": "password_too_short"}

    if accounts_col.find_one({"name": name}):
        return {"ok": False, "reason": "name_exists"}

    # ---- Validate key if provided ----
    bind_func = None
    if key:
        key = key.strip()
        if key.startswith(API_KEY_PREFIX) or key.startswith(ADMIN_KEY_PREFIX):   # 🔥 FF-AD
            key_doc = api_keys_col.find_one({"key": key})
            bind_func = bind_api_key_to_user
        elif key.startswith(LIKE_KEY_PREFIX):
            key_doc = like_keys_col.find_one({"key": key})
            bind_func = bind_like_key_to_user
        else:
            return {"ok": False, "reason": "invalid_key_format"}

        if not key_doc:
            return {"ok": False, "reason": "key_not_found"}

        if key_doc.get("assigned_to"):
            return {"ok": False, "reason": "key_already_assigned",
                    "assigned_to": key_doc["assigned_to"]}

    # ---- Create admin ----
    accounts_col.insert_one({
        "name": name,
        "password_hash": hash_password(password),
        "role": "admin",
        "master_key": None,
        "assigned_api_key": None,
        "assigned_like_key": None,
        "session_token": None,
        "status": "active",
        "created_at": _now(),
        "created_by": created_by,
    })

    # ---- Bind key ----
    if key and bind_func:
        result = bind_func(key, name)
        if not result.get("ok"):
            accounts_col.delete_one({"name": name})
            return result

    return {"ok": True, "name": name, "key": key or None}


# ============================================================
# USER MANAGEMENT
# ============================================================
def list_users(role_filter: str | None = None) -> list:
    q = {}
    if role_filter:
        q["role"] = role_filter
    return list(accounts_col.find(
        q,
        {"_id": 0, "password_hash": 0, "session_token": 0, "session_expires": 0},
    ).sort("created_at", -1))


def delete_user(name: str, by_role: str) -> dict:
    """Admin can only delete users. Owner can delete admins + users."""
    target = accounts_col.find_one({"name": name})
    if not target:
        return {"ok": False, "reason": "not_found"}

    if target.get("role") == "owner":
        return {"ok": False, "reason": "cannot_delete_owner"}

    if target.get("role") == "admin" and by_role != "owner":
        return {"ok": False, "reason": "only_owner_can_delete_admin"}

    accounts_col.delete_one({"name": name})
    return {"ok": True}


def set_user_status(name: str, status: str, by_role: str) -> dict:
    if status not in ("active", "suspended"):
        return {"ok": False, "reason": "invalid_status"}

    target = accounts_col.find_one({"name": name})
    if not target:
        return {"ok": False, "reason": "not_found"}

    if target.get("role") == "owner":
        return {"ok": False, "reason": "cannot_modify_owner"}

    if target.get("role") == "admin" and by_role != "owner":
        return {"ok": False, "reason": "only_owner_can_modify_admin"}

    r = accounts_col.update_one(
        {"name": name},
        {"$set": {"status": status}},
    )
    return {"ok": r.modified_count > 0}

# ============================================================
# SESSION REAL-TIME VALIDATION
# ============================================================
def validate_session_realtime():
    """
    Returns (user, error_response).
    If account disabled/deleted → destroy session, force logout.
    """
    from flask import session as flask_session
    user = current_user()
    if not user:
        return None, ("unauthorized", 401)
    if user.get("status") != "active":
        destroy_session(flask_session.get("token"))
        flask_session.pop("token", None)
        return None, ("account_suspended", 403)
    return user, None