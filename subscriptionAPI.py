"""
subscriptionAPI.py
------------------
API Key management + Boost Like + Auto Like.
"""
from datetime import datetime, timezone, timedelta
import secrets

from config import (
    API_KEY_PREFIX,
    ADMIN_KEY_PREFIX,
    LIKE_KEY_PREFIX,              # 🔥 needed for _is_client_job_valid
    DEFAULT_CREDITS_PER_DAY,
    DEFAULT_DURATION_DAYS,
    REGION_CHOICES,
    REGION_CONFIG,                # 🔥 real config (not empty dict)
)
from db import (
    api_keys_col,
    like_keys_col,                # 🔥 needed for _is_client_job_valid
    accounts_col,
    boost_like_col,
    auto_like_col,
)
from subscription import (
    fetch_player_info,
    send_likes_to_uid,
    _quick_fetch_player_info,     # 🔥 needed by create_boost_job / create_auto_job
)
from logs import log_event


# ============================================================
# SHARED HELPERS
# ============================================================
_ALLOWED = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
# ... rest same


def _chunk(n: int) -> str:
    return "".join(secrets.choice(_ALLOWED) for _ in range(n))


def _gen_key() -> str:
    return f"{API_KEY_PREFIX}-{_chunk(6)}-{_chunk(6)}"


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
# SECTION 1 — API KEY MANAGEMENT
# ============================================================
def generate_api_key(
    credits_per_day: int | None = DEFAULT_CREDITS_PER_DAY,
    duration_days: int = DEFAULT_DURATION_DAYS,
    region: str = "ALL",
    created_by: str = "system",
    admin: bool = False,             # 🔥 NEW
) -> str:
    if credits_per_day is not None and credits_per_day <= 0:
        credits_per_day = None

    region = (region or "ALL").upper()
    if region not in REGION_CHOICES:
        raise ValueError(f"Invalid region: {region}")

    key_type = "unlimited" if credits_per_day is None else "credits"
    prefix = ADMIN_KEY_PREFIX if admin else API_KEY_PREFIX  # 🔥 NEW

    for _ in range(10):
        key = f"{prefix}-{_chunk(6)}-{_chunk(6)}"    # 🔥 use prefix
        if api_keys_col.find_one({"key": key}):
            continue

        api_keys_col.insert_one({
            "key": key,
            "type": key_type,
            "credits_per_day": credits_per_day,
            "region": region,
            "used_today": 0,
            "last_reset_date": _today(),
            "duration_days": duration_days,
            "created_at": _now(),
            "expires_at": _expiry(duration_days),
            "assigned_to": None,
            "assigned_at": None,
            "created_by": created_by,
            "status": "active",
            "is_admin_key": admin,    # 🔥 marker
        })
        return key

    raise RuntimeError("Failed to generate unique API key after 10 attempts")


def bind_api_key_to_user(key: str, username: str) -> dict:
    doc = api_keys_col.find_one({"key": key})
    if not doc:
        return {"ok": False, "reason": "invalid_key"}

    if doc.get("status") == "expired":
        return {"ok": False, "reason": "expired"}

    expires = doc.get("expires_at")
    if expires and expires < _now():
        api_keys_col.delete_one({"key": key})
        return {"ok": False, "reason": "expired"}

    assigned = doc.get("assigned_to")

    if assigned is None:
        api_keys_col.update_one(
            {"key": key},
            {"$set": {"assigned_to": username, "assigned_at": _now()}},
        )
        accounts_col.update_one(
            {"name": username},
            {"$set": {"assigned_api_key": key}},
        )
        return {"ok": True, "reason": "bound", "type": doc.get("type")}

    if assigned == username:
        return {"ok": True, "reason": "already_bound", "type": doc.get("type")}

    return {"ok": False, "reason": "already_assigned", "assigned_to": assigned}


def validate_api_call(key: str, region: str | None = None) -> dict:
    doc = api_keys_col.find_one({"key": key})
    if not doc:
        return {"valid": False, "reason": "invalid_key"}

    if doc.get("status") == "expired":
        return {"valid": False, "reason": "expired"}

    expires = doc.get("expires_at")
    if expires and expires < _now():
        api_keys_col.delete_one({"key": key})
        return {"valid": False, "reason": "expired"}

    if not doc.get("assigned_to"):
        return {"valid": False, "reason": "not_bound"}

    # 🔥 REGION CHECK
    allowed_region = doc.get("region", "ALL")
    if allowed_region != "ALL" and region:
        if allowed_region != region.upper():
            return {
                "valid": False,
                "reason": "region_not_allowed",
                "allowed_region": allowed_region,
                "requested_region": region.upper(),
            }

    today = _today()

    if doc.get("last_reset_date") != today:
        api_keys_col.update_one(
            {"key": key},
            {"$set": {"used_today": 0, "last_reset_date": today}},
        )
        doc["used_today"] = 0
        doc["last_reset_date"] = today

    used = int(doc.get("used_today", 0))

    if doc.get("type") == "unlimited":
        api_keys_col.update_one({"key": key}, {"$inc": {"used_today": 1}})
        return {
            "valid": True, "reason": "ok", "type": "unlimited",
            "used": used + 1, "limit": None, "remaining": None,
        }

    limit = int(doc.get("credits_per_day", 0))
    if used >= limit:
        return {
            "valid": False, "reason": "daily_limit_reached",
            "type": "credits", "used": used, "limit": limit, "remaining": 0,
        }

    api_keys_col.update_one({"key": key}, {"$inc": {"used_today": 1}})
    return {
        "valid": True, "reason": "ok", "type": "credits",
        "used": used + 1, "limit": limit, "remaining": limit - (used + 1),
    }


def reset_daily_credits() -> int:
    today = _today()
    result = api_keys_col.update_many(
        {"last_reset_date": {"$ne": today}},
        {"$set": {"used_today": 0, "last_reset_date": today}},
    )
    return result.modified_count


def remove_expired_keys() -> int:
    result = api_keys_col.delete_many({"expires_at": {"$lt": _now()}})
    return result.deleted_count


def get_api_key_info(key: str) -> dict | None:
    return api_keys_col.find_one({"key": key}, {"_id": 0})


def list_all_api_keys(limit: int = 500) -> list:
    """
    List client API keys only (FF-API-...).
    Admin keys (FF-AD-...) excluded.
    """
    all_keys = list(
        api_keys_col.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
    )
    # 🔥 Safe Python-side filter
    client_keys = [
        k for k in all_keys
        if not str(k.get("key", "")).startswith("FF-AD-")
    ]
    return [_stringify(d) for d in client_keys]


def delete_api_key(key: str) -> bool:
    doc = api_keys_col.find_one({"key": key})
    if not doc:
        return False

    # Delete the key
    api_keys_col.delete_one({"key": key})

    # 🔥 Cascade: if bound to a user, unbind + check orphan
    if doc.get("assigned_to"):
        username = doc["assigned_to"]

        # Unbind
        accounts_col.update_one(
            {"name": username},
            {"$unset": {"assigned_api_key": ""}},
        )

        # Re-fetch to check remaining keys
        user = accounts_col.find_one({"name": username})
        if user and user.get("role") == "user":
            has_api = bool(user.get("assigned_api_key"))
            has_like = bool(user.get("assigned_like_key"))
            if not has_api and not has_like:
                # Orphan user — delete
                accounts_col.delete_one({"name": username})
                print(f"[CASCADE] Deleted orphan user: {username}")

    return True


def count_active_keys() -> dict:
    """Count client keys only (exclude FF-AD-*)."""
    all_keys = list(api_keys_col.find(
        {},
        {"key": 1, "type": 1, "assigned_to": 1, "_id": 0}
    ))
    client_keys = [
        k for k in all_keys
        if not str(k.get("key", "")).startswith("FF-AD-")
    ]
    return {
        "total":     len(client_keys),
        "credits":   sum(1 for k in client_keys if k.get("type") == "credits"),
        "unlimited": sum(1 for k in client_keys if k.get("type") == "unlimited"),
        "bound":     sum(1 for k in client_keys if k.get("assigned_to")),
    }


# ============================================================
# SECTION 2 — BOOST LIKE
# ============================================================
def create_boost_job(uid: str, add_likes: int, per_day: int,
                     region_code: str, created_by: str) -> dict:
    if add_likes <= 0:
        return {"ok": False, "reason": "invalid_add_likes",
                "message": "Likes to add must be greater than 0."}

    if boost_like_col.find_one({"uid": uid, "created_by": created_by}):
        return {"ok": False, "reason": "uid_exists_for_you",
                "message": f"You already have a boost job for UID {uid}."}

    # 🔥 Try quick fetch (3 tokens, fast)
    info = _quick_fetch_player_info(uid, region_code, max_tokens=3)

    if info:
        # Immediate calculation
        current = int(info["likes"])
        target = current + int(add_likes)
        status = "active"
        start_likes = current
        target_likes = target
        nickname = info["nickname"]
        init_msg = f"Job active: {current} → {target} (+{add_likes})"
    else:
        # Pending — scheduler will init soon
        status = "pending"
        start_likes = None
        target_likes = None
        nickname = None
        init_msg = "Job created. Initializing via scheduler (max 15 min)."

    boost_like_col.insert_one({
        "uid": uid,
        "region": region_code.upper(),
        "add_likes": int(add_likes),
        "per_day": int(per_day),
        "status": status,
        "start_likes": start_likes,
        "target_likes": target_likes,
        "nickname": nickname,
        "created_at": _now(),
        "created_by": created_by,
        "owner": created_by,
        "initialized_at": _now() if info else None,
        "last_run": None,
        "run_count": 0,
        "success_count": 0,
        "fail_count": 0,
        "last_error": None,
    })

    log_event(created_by, "boost_create", uid=uid,
              add_likes=int(add_likes), region=region_code.upper(),
              start_likes=start_likes, target=target_likes,
              status=status,
              added_by=created_by, broadcast=False)

    return {
        "ok": True,
        "status": status,
        "start_likes": start_likes,
        "target_likes": target_likes,
        "add_likes": int(add_likes),
        "message": init_msg,
    }


def list_boost_jobs() -> list:
    return [_stringify(d) for d in
            boost_like_col.find({}, {"_id": 0}).sort("created_at", -1)]


def delete_boost_job(uid: str) -> bool:
    r = boost_like_col.delete_one({"uid": uid})
    return r.deleted_count > 0


def pause_boost_job(uid: str) -> bool:
    r = boost_like_col.update_one({"uid": uid}, {"$set": {"status": "paused"}})
    return r.modified_count > 0


def resume_boost_job(uid: str) -> bool:
    r = boost_like_col.update_one({"uid": uid}, {"$set": {"status": "active"}})
    return r.modified_count > 0


def run_boost_jobs() -> dict:
    """
    Process boost jobs:
    - 'pending' → initialize (fetch player info, set start/target)
    - 'active'  → send likes, check target
    """
    jobs = list(boost_like_col.find({"status": {"$in": ["pending", "active"]}}))
    summary = {
        "processed": 0, "completed": 0, "failed": 0,
        "initialized": 0, "terminated": 0, "results": []
    }

    for job in jobs:
        # Owner key validity check
        valid, reason = _is_client_job_valid(job)
        if not valid:
            boost_like_col.update_one(
                {"_id": job["_id"]},
                {"$set": {"status": "terminated",
                          "terminated_at": _now(),
                          "terminate_reason": reason}},
            )
            summary["terminated"] += 1
            log_event(added_by, "boost_terminate", uid=job["uid"], reason=reason, broadcast=False)
            continue

        uid = job["uid"]
        region = job["region"]
        add_likes = int(job.get("add_likes", 0))
        added_by = job.get("created_by", "system")

        # ============ INITIALIZATION (pending → active) ============
        if job["status"] == "pending" or not job.get("start_likes"):
            info = fetch_player_info(uid, region)
            if not info:
                # Can't fetch — keep pending, retry next run
                boost_like_col.update_one(
                    {"_id": job["_id"]},
                    {"$set": {"last_error": "token_fetch_failed",
                              "last_run": _now()},
                     "$inc": {"fail_count": 1}},
                )
                summary["failed"] += 1
                continue

            current = int(info["likes"])
            target = current + add_likes

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
            job["start_likes"] = current
            job["target_likes"] = target
            job["nickname"] = info["nickname"]
            job["status"] = "active"
            summary["initialized"] += 1
            print(f"[boost] Initialized UID {uid}: {current} → {target} (+{add_likes})")

        # ============ DAILY RUN ============
        target = int(job["target_likes"])
        start_likes = int(job["start_likes"])

        try:
            result = send_likes_to_uid(uid, region)
        except Exception as e:
            result = {"error": str(e), "status": 0}

        if result.get("error"):
            summary["failed"] += 1
            boost_like_col.update_one(
                {"_id": job["_id"]},
                {"$set": {"last_error": result["error"], "last_run": _now()},
                 "$inc": {"fail_count": 1, "run_count": 1}},
            )
            log_event(added_by, "boost_fail", uid=uid, error=result["error"])
            continue

        after = int(result.get("after", 0))
        added = int(result.get("added", 0))

        boost_like_col.update_one(
            {"_id": job["_id"]},
            {"$set": {"last_run": _now(), "last_error": None},
             "$inc": {"run_count": 1, "success_count": 1}},
        )

        log_payload = {
            "uid": uid,
            "region": result.get("region", region),
            "nickname": result.get("nickname"),
            "added_by": added_by,
            "start_likes": start_likes,
            "before": result.get("before"),
            "after": after,
            "added": added,
            "tokens_used": result.get("tokens_used"),
            "target": target,
        }

        if after >= target:
            boost_like_col.update_one(
                {"_id": job["_id"]},
                {"$set": {"status": "completed", "completed_at": _now()}},
            )
            summary["completed"] += 1
            log_event(added_by, "boost_complete", **log_payload)
        else:
            log_event(added_by, "boost_run", **log_payload)

        summary["processed"] += 1
        summary["results"].append({
            "uid": uid, "added": added, "current": after, "target": target,
        })

    return summary


def run_auto_jobs() -> dict:
    jobs = list(auto_like_col.find({"status": {"$in": ["pending", "active"]}}))
    summary = {
        "processed": 0, "expired": 0, "failed": 0,
        "initialized": 0, "terminated": 0, "results": []
    }

    for job in jobs:
        valid, reason = _is_client_job_valid(job)
        if not valid:
            auto_like_col.update_one(
                {"_id": job["_id"]},
                {"$set": {"status": "terminated",
                          "terminated_at": _now(),
                          "terminate_reason": reason}},
            )
            summary["terminated"] += 1
            continue

        uid = job["uid"]
        region = job["region"]
        expires = job.get("expires_at")
        added_by = job.get("created_by", "system")

        # 🔥 Expiry check
        if expires and expires < _now():
            auto_like_col.update_one(
                {"_id": job["_id"]},
                {"$set": {"status": "expired", "expired_at": _now()}},
            )
            summary["expired"] += 1
            log_event(added_by, "auto_expired", uid=uid)
            continue

        # ============ INITIALIZATION ============
        if job["status"] == "pending" or not job.get("start_likes"):
            info = fetch_player_info(uid, region)
            if not info:
                auto_like_col.update_one(
                    {"_id": job["_id"]},
                    {"$set": {"last_error": "token_fetch_failed",
                              "last_run": _now()},
                     "$inc": {"fail_count": 1}},
                )
                summary["failed"] += 1
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
            job["start_likes"] = info["likes"]
            job["nickname"] = info["nickname"]
            job["status"] = "active"
            summary["initialized"] += 1
            print(f"[auto] Initialized UID {uid}: start={info['likes']}")

        # ============ DAILY RUN ============
        try:
            result = send_likes_to_uid(uid, region)
        except Exception as e:
            result = {"error": str(e), "status": 0}

        if result.get("error"):
            summary["failed"] += 1
            auto_like_col.update_one(
                {"_id": job["_id"]},
                {"$set": {"last_error": result["error"], "last_run": _now()},
                 "$inc": {"fail_count": 1, "run_count": 1}},
            )
            continue

        auto_like_col.update_one(
            {"_id": job["_id"]},
            {"$set": {"last_run": _now(), "last_error": None},
             "$inc": {"run_count": 1, "success_count": 1}},
        )
        log_event(
            "added_by", "auto_run",
            uid=uid,
            region=result.get("region", region),
            nickname=result.get("nickname"),
            added_by=added_by,
            before=result.get("before"),
            after=result.get("after"),
            added=result.get("added"),
            tokens_used=result.get("tokens_used"),
            expires_at=expires.isoformat() if expires else None,
        )
        summary["processed"] += 1

    return summary


# ============================================================
# SECTION 3 — AUTO LIKE
# ============================================================
def create_auto_job(uid: str, per_day: int, duration_days: int,
                    region_code: str, created_by: str) -> dict:
    if auto_like_col.find_one({"uid": uid, "created_by": created_by}):
        return {"ok": False, "reason": "uid_exists_for_you",
                "message": f"You already have an auto like job for UID {uid}."}

    expires = _now() + timedelta(days=int(duration_days))

    # 🔥 Try quick fetch
    info = _quick_fetch_player_info(uid, region_code, max_tokens=3)

    if info:
        status = "active"
        start_likes = info["likes"]
        nickname = info["nickname"]
        init_msg = f"Job active: start={start_likes}"
    else:
        status = "pending"
        start_likes = None
        nickname = None
        init_msg = "Job created. Initializing via scheduler (max 15 min)."

    auto_like_col.insert_one({
        "uid": uid,
        "region": region_code.upper(),
        "per_day": int(per_day),
        "duration_days": int(duration_days),
        "expires_at": expires,
        "status": status,
        "start_likes": start_likes,
        "nickname": nickname,
        "created_at": _now(),
        "created_by": created_by,
        "owner": created_by,
        "initialized_at": _now() if info else None,
        "last_run": None,
        "run_count": 0,
        "success_count": 0,
        "fail_count": 0,
        "last_error": None,
    })

    log_event(created_by, "auto_create", uid=uid,
              per_day=per_day, days=duration_days,
              region=region_code.upper(),
              start_likes=start_likes, status=status,
              added_by=created_by, broadcast=False)

    return {
        "ok": True,
        "status": status,
        "start_likes": start_likes,
        "expires_at": expires.isoformat(),
        "message": init_msg,
    }


def list_auto_jobs() -> list:
    return [_stringify(d) for d in
            auto_like_col.find({}, {"_id": 0}).sort("created_at", -1)]


def delete_auto_job(uid: str) -> bool:
    r = auto_like_col.delete_one({"uid": uid})
    return r.deleted_count > 0


def pause_auto_job(uid: str) -> bool:
    r = auto_like_col.update_one({"uid": uid}, {"$set": {"status": "paused"}})
    return r.modified_count > 0


def resume_auto_job(uid: str) -> bool:
    r = auto_like_col.update_one({"uid": uid}, {"$set": {"status": "active"}})
    return r.modified_count > 0


def _is_client_job_valid(job: dict) -> tuple[bool, str]:
    """
    Check if job's owner key is still valid.
    Returns (valid, reason).
    """
    owner = job.get("created_by")
    if not owner or owner in ("system", "sarker"):
        return True, "ok"   # Owner system jobs always valid

    # Find owner's account
    from db import accounts_col
    user = accounts_col.find_one({"name": owner})
    if not user:
        return False, "owner_deleted"

    if user.get("status") != "active":
        return False, "owner_suspended"

    # Check key
    key_str = user.get("assigned_api_key") or user.get("assigned_like_key")
    if not key_str:
        return False, "no_key"

    if key_str.startswith(API_KEY_PREFIX):
        key_doc = api_keys_col.find_one({"key": key_str})
    else:
        key_doc = like_keys_col.find_one({"key": key_str})

    if not key_doc:
        return False, "key_deleted"

    if key_doc.get("expires_at") and key_doc["expires_at"] < _now():
        return False, "key_expired"

    # Check credit limit (if credits type)
    if key_doc.get("type") == "credits":
        used = int(key_doc.get("used_today", 0))
        limit = int(key_doc.get("credits_per_day", 0))
        if limit and used >= limit:
            return False, "daily_limit_reached"

    return True, "ok"

def check_token_pool(region_code: str, sample_size: int = 10) -> dict:
    """
    Quick validation — try up to N tokens with a test UID.
    Returns: {ok: bool, total: int, valid: int, needs_refresh: bool}
    """
    import random
    from app.encryption import enc
    from app.request_handler import make_request
    from db import db

    region = (region_code or "").upper()
    config = REGION_CONFIG.get(region)
    if not config:
        raise ValueError(f"Unsupported region code: {region or '<empty>'}")

    tokens_col = db[config["tokens"]]
    all_tokens = list(tokens_col.find({}, {"_id": 0, "token": 1}))

    total = len(all_tokens)
    if not all_tokens:
        return {"ok": False, "total": 0, "valid": 0, "needs_refresh": True,
                "message": "No tokens in pool"}

    # Use a well-known test UID (should return valid protobuf for any token)
    # Actually, we just check response is not empty / not a string error
    test_uid = "1"          # minimal — some tokens may return valid-ish protobuf
    encrypted = enc(test_uid)
    if not encrypted:
        return {"ok": False, "total": total, "valid": 0, "needs_refresh": True,
                "message": "Encryption failed"}

    url_info = config["url"] + "/GetPlayerPersonalShow"
    sample = all_tokens[:sample_size]
    random.shuffle(sample)

    valid_count = 0
    for token_doc in sample:
        result = make_request(encrypted, url_info, token_doc["token"])
        if result:              # parse success → valid
            valid_count += 1

    # Heuristic: if < 30% valid → needs refresh
    needs_refresh = total < 30 or valid_count < max(1, sample_size * 0.3)

    return {
        "ok": valid_count > 0,
        "total": total,
        "valid": valid_count,
        "sampled": len(sample),
        "needs_refresh": needs_refresh,
    }