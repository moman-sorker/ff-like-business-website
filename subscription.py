"""
subscription.py
---------------
Like Key management + Like sender core.
Merged from: subscription.py + like_sender.py
"""
from datetime import datetime, timezone, timedelta
import secrets
import asyncio

from config import (
    LIKE_KEY_PREFIX,
    DEFAULT_PER_UID_PER_DAY,
    DEFAULT_DURATION_DAYS,
    REGION_CONFIG,
)
from db import (
    like_keys_col, like_usage_col, accounts_col, db,
    boost_like_col, auto_like_col,      # 🔥 ei 2 ta add koro
)
from app.encryption import enc
from app.request_handler import make_request, send_multiple_requests


# ============================================================
# SHARED HELPERS
# ============================================================
_ALLOWED = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _chunk(n: int) -> str:
    return "".join(secrets.choice(_ALLOWED) for _ in range(n))


def _gen_key() -> str:
    return f"{LIKE_KEY_PREFIX}-{_chunk(6)}-{_chunk(6)}"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _today() -> str:
    return _now().strftime("%Y-%m-%d")


def _expiry(days: int) -> datetime:
    return _now() + timedelta(days=days)


def _stringify(doc: dict) -> dict:
    if not doc:
        return None
    out = {}
    for k, v in doc.items():
        out[k] = v.isoformat() if isinstance(v, datetime) else v
    return out


# ============================================================
# SECTION 1 — LIKE KEY MANAGEMENT
# ============================================================
def generate_like_key(
    per_uid_per_day: int = DEFAULT_PER_UID_PER_DAY,
    duration_days: int = DEFAULT_DURATION_DAYS,
    created_by: str = "system",
) -> str:
    if per_uid_per_day <= 0:
        raise ValueError("per_uid_per_day must be > 0")

    for _ in range(10):
        key = _gen_key()
        if like_keys_col.find_one({"key": key}):
            continue

        like_keys_col.insert_one({
            "key": key,
            "per_uid_per_day": per_uid_per_day,
            "duration_days": duration_days,
            "created_at": _now(),
            "expires_at": _expiry(duration_days),
            "assigned_to": None,
            "assigned_at": None,
            "created_by": created_by,
            "status": "active",
        })
        return key

    raise RuntimeError("Failed to generate unique Like key after 10 attempts")


def bind_like_key_to_user(key: str, username: str) -> dict:
    doc = like_keys_col.find_one({"key": key})
    if not doc:
        return {"ok": False, "reason": "invalid_key"}

    if doc.get("status") == "expired":
        return {"ok": False, "reason": "expired"}

    expires = doc.get("expires_at")
    if expires and expires < _now():
        like_keys_col.delete_one({"key": key})
        return {"ok": False, "reason": "expired"}

    assigned = doc.get("assigned_to")

    if assigned is None:
        like_keys_col.update_one(
            {"key": key},
            {"$set": {"assigned_to": username, "assigned_at": _now()}},
        )
        accounts_col.update_one(
            {"name": username},
            {"$set": {"assigned_like_key": key}},
        )
        return {"ok": True, "reason": "bound"}

    if assigned == username:
        return {"ok": True, "reason": "already_bound"}

    return {"ok": False, "reason": "already_assigned", "assigned_to": assigned}


def validate_like_call(key: str, uid: str) -> dict:
    doc = like_keys_col.find_one({"key": key})
    if not doc:
        return {"valid": False, "reason": "invalid_key"}

    if doc.get("status") == "expired":
        return {"valid": False, "reason": "expired"}

    expires = doc.get("expires_at")
    if expires and expires < _now():
        like_keys_col.delete_one({"key": key})
        return {"valid": False, "reason": "expired"}

    if not doc.get("assigned_to"):
        return {"valid": False, "reason": "not_bound"}

    per_day = int(doc.get("per_uid_per_day", 0))
    today = _today()
    uid_str = str(uid)

    usage = like_usage_col.find_one({"key": key, "date": today}) or {"uids": {}}
    used = int(usage.get("uids", {}).get(uid_str, 0))

    if used >= per_day:
        return {
            "valid": False,
            "reason": "uid_daily_limit_reached",
            "used": used,
            "limit": per_day,
            "remaining": 0,
        }

    like_usage_col.update_one(
        {"key": key, "date": today},
        {
            "$inc": {f"uids.{uid_str}": 1},
            "$setOnInsert": {"key": key, "date": today},
        },
        upsert=True,
    )

    return {
        "valid": True,
        "reason": "ok",
        "used": used + 1,
        "limit": per_day,
        "remaining": per_day - (used + 1),
    }


def reset_daily_like_usage() -> int:
    today = _today()
    result = like_usage_col.delete_many({"date": {"$lt": today}})
    return result.deleted_count


def remove_expired_like_keys() -> int:
    result = like_keys_col.delete_many({"expires_at": {"$lt": _now()}})
    return result.deleted_count


def get_like_key_info(key: str) -> dict | None:
    return like_keys_col.find_one({"key": key}, {"_id": 0})


def list_all_like_keys(limit: int = 500) -> list:
    return [_stringify(d) for d in
            like_keys_col.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)]


def get_like_usage_summary(key: str) -> list:
    return [_stringify(d) for d in
            like_usage_col.find({"key": key}, {"_id": 0}).sort("date", -1).limit(30)]


def delete_like_key(key: str) -> bool:
    doc = like_keys_col.find_one({"key": key})
    if not doc:
        return False

    like_keys_col.delete_one({"key": key})
    like_usage_col.delete_many({"key": key})

    if doc.get("assigned_to"):
        username = doc["assigned_to"]

        accounts_col.update_one(
            {"name": username},
            {"$unset": {"assigned_like_key": ""}},
        )

        user = accounts_col.find_one({"name": username})
        if user and user.get("role") == "user":
            has_api = bool(user.get("assigned_api_key"))
            has_like = bool(user.get("assigned_like_key"))
            if not has_api and not has_like:
                accounts_col.delete_one({"name": username})
                print(f"[CASCADE] Deleted orphan user: {username}")

    return True


def count_active_like_keys() -> dict:
    return {
        "total":   like_keys_col.count_documents({}),
        "bound":   like_keys_col.count_documents({"assigned_to": {"$ne": None}}),
        "unbound": like_keys_col.count_documents({"assigned_to": None}),
    }


# ============================================================
# SECTION 2 — LIKE SENDER CORE
# ============================================================
def resolve_region(region_code: str) -> str:
    """Public — used by /like route for region check."""
    rc = (region_code or "").upper()
    if rc == "IND":
        return "IND"
    if rc in ("US", "BR", "SAC", "NA", "NX"):
        return "NX"
    if rc in ("AG", "AG2"):
        return "AG"
    return "AG"


def fetch_player_info(uid: str, region_code: str) -> dict | None:
    """Fetch current likes/nickname/region."""
    import random

    region = resolve_region(region_code)
    config = REGION_CONFIG[region]
    all_tokens = list(db[config["tokens"]].find({}, {"_id": 0, "token": 1}))
    if not all_tokens:
        return None

    encrypted_uid = enc(uid)
    if not encrypted_uid:
        return None

    url_info = config["url"] + "/GetPlayerPersonalShow"

    # 🔥 Shuffle + try all tokens (until one works)
    shuffled = all_tokens[:]
    random.shuffle(shuffled)
    
    for token_doc in shuffled:
        token = token_doc["token"]
        result = make_request(encrypted_uid, url_info, token)
        if result:
            return {
                "uid": uid,
                "nickname": result.AccountInfo.PlayerNickname,
                "player_region": result.AccountInfo.PlayerRegion,
                "level": result.AccountInfo.Levels,
                "likes": int(result.AccountInfo.Likes),
            }
    return None

def _quick_fetch_player_info(uid: str, region_code: str, max_tokens: int = 3) -> dict | None:
    """
    Fast fetch — try only N tokens. Used for job initialization.
    Returns player info dict or None.
    """
    import random
    region = resolve_region(region_code)
    config = REGION_CONFIG[region]
    tokens = list(db[config["tokens"]].find({}, {"_id": 0, "token": 1}))
    if not tokens:
        return None

    encrypted = enc(uid)
    if not encrypted:
        return None

    url_info = config["url"] + "/GetPlayerPersonalShow"
    random.shuffle(tokens)

    for token_doc in tokens[:max_tokens]:
        result = make_request(encrypted, url_info, token_doc["token"])
        if result:
            return {
                "nickname": result.AccountInfo.PlayerNickname,
                "player_region": result.AccountInfo.PlayerRegion,
                "level": result.AccountInfo.Levels,
                "likes": int(result.AccountInfo.Likes),
            }
    return None


def initialize_pending_jobs() -> dict:
    """
    Runs periodically — initializes pending boost + auto jobs.
    Called from scheduler every 15 min.
    """
    summary = {"boost_init": 0, "auto_init": 0}

    # ============ BOOST ============
    pending_boost = list(boost_like_col.find({"status": "pending"}))
    for job in pending_boost:
        info = _quick_fetch_player_info(job["uid"], job["region"], max_tokens=5)
        if not info:
            continue
        current = int(info["likes"])
        target = current + int(job["add_likes"])
        boost_like_col.update_one(
            {"_id": job["_id"]},
            {"$set": {
                "start_likes": current,
                "target_likes": target,
                "nickname": info["nickname"],
                "status": "active",
                "initialized_at": _now(),
                "last_error": None,
            }},
        )
        summary["boost_init"] += 1
        print(f"[init] Boost {job['uid']}: {current} → {target} (+{job['add_likes']})")

    # ============ AUTO ============
    pending_auto = list(auto_like_col.find({"status": "pending"}))
    for job in pending_auto:
        info = _quick_fetch_player_info(job["uid"], job["region"], max_tokens=5)
        if not info:
            continue
        auto_like_col.update_one(
            {"_id": job["_id"]},
            {"$set": {
                "start_likes": info["likes"],
                "nickname": info["nickname"],
                "status": "active",
                "initialized_at": _now(),
                "last_error": None,
            }},
        )
        summary["auto_init"] += 1
        print(f"[init] Auto {job['uid']}: start={info['likes']}")

    return summary

def send_likes_to_uid(uid: str, region_code: str, tokens: list | None = None) -> dict:
    """Main like-sending function. Caller handles credits/key validation."""
    region = resolve_region(region_code)
    config = REGION_CONFIG[region]
    tokens_col = db[config["tokens"]]

    if tokens is None:
        tokens = list(tokens_col.find({}, {"_id": 0, "token": 1}))

    if not tokens:
        return {"error": "no_tokens", "status": 0}

    encrypted_uid = enc(uid)
    if not encrypted_uid:
        return {"error": "encrypt_failed", "status": 0}

    base_url = config["url"]
    url_info = base_url + "/GetPlayerPersonalShow"
    url_like = base_url + "/LikeProfile"

    # ---------------- BEFORE ----------------
    import random
    valid_token = None
    before_data = None
    shuffled = tokens[:]
    random.shuffle(shuffled)
    for token_doc in shuffled:
        token = token_doc["token"]
        result = make_request(encrypted_uid, url_info, token)
        if result:
            valid_token = token
            before_data = result
            break

    if not before_data:
        # 🔥 Check if this UID was liked recently (24h window)
        from db import activity_logs_col
        recent = activity_logs_col.find_one({
            "action": "like",
            "uid": str(uid),
            "status": 1,
            "timestamp": {"$gte": _now() - timedelta(hours=24)},
        })

        if recent:
            return {
                "error": "uid_daily_limit_reached",
                "status": 2,
                "message": "This UID already received max likes today. "
                           "Try again after 24h (next UTC reset).",
                "last_like_at": recent.get("timestamp").isoformat() if recent.get("timestamp") else None,
            }

        return {
            "error": "invalid_account_or_server",
            "status": 0,
            "tokens_tried": len(tokens),
            "hint": "All tokens failed. Either all are daily-limit exhausted "
                    "or player UID is invalid. Try again later.",
        }

    before_like   = int(before_data.AccountInfo.Likes)
    player_name   = before_data.AccountInfo.PlayerNickname
    player_region = before_data.AccountInfo.PlayerRegion
    player_level  = before_data.AccountInfo.Levels

    # ---------------- SEND ----------------
    results = asyncio.run(send_multiple_requests(uid, region, url_like, tokens))

    # 🔥 FIX: DO NOT delete tokens on daily limit
    # The limit is per-UID-per-token, not permanent.
    # Same token can still like OTHER UIDs.
    tokens_failed_this_uid = [
        r.get("token")
        for r in results
        if isinstance(r, dict)
        and r.get("response", "").strip() == "BR_ACCOUNT_DAILY_LIKE_PROFILE_LIMIT"
        and r.get("status") != 200
        and r.get("token")
    ]
    # (no delete_many — tokens stay in DB)

    # ---------------- AFTER ----------------
    after_data = make_request(encrypted_uid, url_info, valid_token)
    if not after_data:
        return {"error": "after_failed", "status": 0}

    after_like = int(after_data.AccountInfo.Likes)
    like_diff = after_like - before_like

    return {
        "status": 1 if like_diff > 0 else 2,
        "uid": uid,
        "region": player_region,
        "nickname": player_name,
        "level": player_level,
        "before": before_like,
        "after": after_like,
        "added": like_diff,
        "tokens_used": len(tokens),
        "tokens_deleted": 0,                    # 🔥 always 0
        "tokens_failed_this_uid": len(tokens_failed_this_uid),   # 🔥 info
    }