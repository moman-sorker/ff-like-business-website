# -*- coding: utf-8 -*-
"""
main.py — Flask app entry.
"""
import asyncio
import threading
import urllib3
from datetime import datetime, timezone

from flask import Flask, request, jsonify, render_template, session as flask_session
from dotenv import load_dotenv

# ---- DB ----
from db import (
    accounts_col, api_keys_col, like_keys_col,
    boost_like_col, auto_like_col, activity_logs_col,
)

# ---- Config ----
from config import (
    ADMIN_KEY_PREFIX, PORT, MONGO_URI, DB_NAME,
    API_KEY_PREFIX, LIKE_KEY_PREFIX,
    OWNER_KEY,
)

# ---- Auth ----
from auth import (
    authenticate, create_session, destroy_session, current_user,
    login_required, admin_required, owner_required,
    create_admin,                                          # 🔥
    list_users, delete_user, set_user_status,
)

# ---- Subscription ----
from subscription import (
    generate_like_key, validate_like_call, get_like_key_info,
    list_all_like_keys, delete_like_key, count_active_like_keys,
    get_like_usage_summary,
    resolve_region,
    send_likes_to_uid,
    reset_daily_like_usage, remove_expired_like_keys,
)

from subscriptionAPI import (
    generate_api_key, validate_api_call, get_api_key_info,
    list_all_api_keys, delete_api_key, count_active_keys,
    create_boost_job, list_boost_jobs, delete_boost_job,
    pause_boost_job, resume_boost_job,
    create_auto_job, list_auto_jobs, delete_auto_job,
    pause_auto_job, resume_auto_job,
    reset_daily_credits, remove_expired_keys,
    run_boost_jobs, run_auto_jobs,
    REGION_CHOICES,
)

# ---- Logs ----
from logs import (
    log_action, log_event,
    get_recent_logs, get_stats_today,
    broadcast_log, start_bots,
    send_telegram_log, send_discord_log,                   # 🔥 (after logs.py fix)
    list_bot_settings, mask_value,
)

# ---- Tokens ----
from tokens_handler import start_token_manager

# ---- APScheduler ----
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger


load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__, template_folder="templates", static_folder="templates/static")

@app.errorhandler(500)
def internal_error(error):
    import traceback
    traceback.print_exc()
    return jsonify({
        "error": "server_error",
        "message": "An internal error occurred. Please try again.",
    }), 500

app.secret_key = __import__("config").SECRET_KEY
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

scheduler = BackgroundScheduler(timezone="UTC")

# ============================================================
# PAGES
# ============================================================
@app.route("/")
def page_index():
    try:
        return render_template("index.html")
    except Exception:
        return "index.html missing", 200


@app.route("/admin")
def page_admin():
    try:
        return render_template("admin.html")
    except Exception:
        return "admin.html missing", 200


@app.route("/clients")
def page_clients():
    try:
        return render_template("clients.html")
    except Exception:
        return "clients.html missing", 200


# ============================================================
# PUBLIC API — /like  and  /status
# ============================================================
@app.route("/like", methods=["GET"])
def like_endpoint():
    uid = request.args.get("uid")
    region = (request.args.get("region") or "").upper()
    key = request.args.get("key")

    if not uid or not region or not key:
        return jsonify({"error": "uid, region, key required"}), 400

    # ============ 🔥 OWNER BYPASS ============
    if key == OWNER_KEY:
        result = send_likes_to_uid(uid, region)
        log_event(
            "owner", "like",
            uid=uid, region=region,
            nickname=result.get("nickname"),
            before=result.get("before"),
            after=result.get("after"),
            added=result.get("added"),
            tokens_used=result.get("tokens_used"),
            status=result.get("status"),
            limit=None, remaining=None,
            error=result.get("error"),
        )
        return jsonify(result), (200 if not result.get("error") else 500)

    # ============ SUBSCRIPTION KEYS ============
    if key.startswith(API_KEY_PREFIX) or key.startswith(ADMIN_KEY_PREFIX):    # 🔥
        resolved = resolve_region(region)
        validation = validate_api_call(key, resolved)
        key_type = "api"
    elif key.startswith(LIKE_KEY_PREFIX):
        validation = validate_like_call(key, uid)
        key_type = "like"
    else:
        return jsonify({"error": "invalid_key_format"}), 400

    if not validation.get("valid"):
        return jsonify({
            "error": validation.get("reason"),
            "validation": validation,
        }), 403

    result = send_likes_to_uid(uid, region)

    owner_doc = api_keys_col.find_one({"key": key}, {"assigned_to": 1}) or \
                like_keys_col.find_one({"key": key}, {"assigned_to": 1})
    username = (owner_doc or {}).get("assigned_to", "unknown")

    log_event(
        username, "like",
        uid=uid, region=region,
        nickname=result.get("nickname"),
        before=result.get("before"),
        after=result.get("after"),
        added=result.get("added"),
        tokens_used=result.get("tokens_used"),
        status=result.get("status"),
        limit=validation.get("limit"),
        remaining=validation.get("remaining"),
        error=result.get("error"),
    )

    result["key_info"] = validation
    return jsonify(result), (200 if not result.get("error") else 500)


@app.route("/status", methods=["GET"])
def status_endpoint():
    key = request.args.get("key")
    if not key:
        return jsonify({"error": "key required"}), 400

    if key.startswith(API_KEY_PREFIX) or key.startswith(ADMIN_KEY_PREFIX):
        doc = api_keys_col.find_one({"key": key}, {"_id": 0})
    elif key.startswith(LIKE_KEY_PREFIX):
        doc = like_keys_col.find_one({"key": key}, {"_id": 0})
    else:
        return jsonify({"error": "invalid_key_format"}), 400

    if not doc:
        return jsonify({"error": "invalid_key"}), 404

    return jsonify(_stringify_doc(doc))


# ============================================================
# AUTH
# ============================================================
@app.route("/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "").strip()
    password = data.get("password") or ""
    key = (data.get("key") or "").strip()
    like_key = (data.get("like_key") or "").strip()   # 🔥 NEW

    if not name or not password:
        return jsonify({"error": "name and password required"}), 400

    result = authenticate(name, password, key, like_key)   # 🔥 pass both
    if not result.get("ok"):
        log_action(name, "login_fail", reason=result.get("reason"))
        return jsonify({"error": result.get("reason", "login_failed")}), 401

    user = result["user"]
    token = create_session(user["name"])
    flask_session["token"] = token

    log_action(user["name"], "login", role=user.get("role"))

    # 🔥 Re-fetch user to get latest assigned keys
    user = accounts_col.find_one({"name": user["name"]})

    return jsonify({
        "ok": True,
        "user": {
            "name": user["name"],
            "role": user.get("role"),
            "assigned_api_key": user.get("assigned_api_key"),
            "assigned_like_key": user.get("assigned_like_key"),
        },
    })


@app.route("/auth/logout", methods=["POST"])
def auth_logout():
    token = flask_session.get("token")
    user = current_user()
    if user:
        log_action(user["name"], "logout")
    destroy_session(token)
    flask_session.pop("token", None)
    return jsonify({"ok": True})

@app.route("/auth/heartbeat", methods=["GET"])
def auth_heartbeat():
    """
    Lightweight session check — called every 3s by realtime.js.
    Returns user data if valid, 401 if not.
    Also detects: suspended, deleted, expired sessions.
    """
    from flask import session as flask_session
    user = current_user()
    if not user:
        return jsonify({"valid": False, "reason": "unauthorized"}), 401

    if user.get("status") != "active":
        destroy_session(flask_session.get("token"))
        flask_session.pop("token", None)
        return jsonify({"valid": False, "reason": "account_suspended"}), 403

    return jsonify({
        "valid": True,
        "user": {
            "name": user["name"],
            "role": user.get("role"),
            "status": user.get("status"),
        },
    })

@app.route("/auth/me", methods=["GET"])
@login_required
def auth_me():
    user = current_user()
    api_key_doc = None
    like_key_doc = None

    if user.get("assigned_api_key"):
        api_key_doc = api_keys_col.find_one(
            {"key": user["assigned_api_key"]},
            {"_id": 0, "assigned_to": 0},
        )
    if user.get("assigned_like_key"):
        like_key_doc = like_keys_col.find_one(
            {"key": user["assigned_like_key"]},
            {"_id": 0, "assigned_to": 0},
        )

    return jsonify({
        "user": {
            "name": user["name"],
            "role": user.get("role"),
            "status": user.get("status"),
            "created_at": user.get("created_at").isoformat() if user.get("created_at") else None,
        },
        "api_key": _stringify_doc(api_key_doc) if api_key_doc else None,
        "like_key": _stringify_doc(like_key_doc) if like_key_doc else None,
    })


# ============================================================
# ADMIN — Users
# ============================================================
@app.route("/admin/users", methods=["GET"])
@admin_required
def admin_list_users():
    me = current_user()
    if me.get("role") == "owner":
        users = list_users()                # all
    else:
        users = list_users(role_filter="user")   # admin sees only users
    return jsonify({"users": users})


# ============================================================
# ADMIN — Create Admin (owner only)
# ============================================================
@app.route("/admin/admins/create", methods=["POST"])
@owner_required
def admin_create_admin():
    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "").strip()
    password = data.get("password") or ""
    key = (data.get("key") or "").strip()

    if not name or not password:
        return jsonify({"error": "name and password required"}), 400

    me = current_user()
    result = create_admin(name, password,
                          created_by=me["name"],
                          key=key or None)
    if not result.get("ok"):
        return jsonify({"error": result.get("reason")}), 400

    log_action(me["name"], "admin_create", new_admin=name,
               key_provided=bool(key))
    return jsonify({"ok": True, "name": name, "key": result.get("key")})

@app.route("/admin/owner-key-preview", methods=["GET"])
@admin_required                                          # 🔥 owner → admin
def admin_owner_key_preview():
    me = current_user()
    if me.get("role") == "owner":
        from config import OWNER_KEY
        return jsonify({"key": OWNER_KEY, "is_owner": True})
    else:
        # Admin — return their own assigned key
        key = me.get("assigned_api_key") or me.get("assigned_like_key") or "—"
        return jsonify({"key": key, "is_owner": False})

@app.route("/admin/like", methods=["POST"])
@admin_required                                          # 🔥 owner → admin
def admin_direct_like():
    me = current_user()
    data = request.get_json(silent=True) or {}
    uid = str(data.get("uid", "")).strip()
    region = (data.get("region") or "").upper()

    if not uid or not region:
        return jsonify({"error": "uid and region required"}), 400

    role = me.get("role")

    # ============ OWNER — bypass, no credits ============
    if role == "owner":
        result = send_likes_to_uid(uid, region)
        log_action(me["name"], "like", uid=uid, region=region,
                   nickname=result.get("nickname"),
                   before=result.get("before"), after=result.get("after"),
                   added=result.get("added"),
                   tokens_used=result.get("tokens_used"),
                   status=result.get("status"),
                   owner_bypass=True,
                   error=result.get("error"))
        return jsonify(result), (200 if not result.get("error") else 500)

    # ============ ADMIN — use assigned key ============
    key = me.get("assigned_api_key") or me.get("assigned_like_key")
    if not key:
        return jsonify({
            "error": "no_key_assigned",
            "message": "You don't have an assigned key. Ask owner to assign one.",
        }), 403

    # Validate key
    if key.startswith(API_KEY_PREFIX) or key.startswith(ADMIN_KEY_PREFIX):
        validation = validate_api_call(key, resolve_region(region))
        key_type = "api"
    elif key.startswith(LIKE_KEY_PREFIX):
        validation = validate_like_call(key, uid)
        key_type = "like"
    else:
        return jsonify({"error": "invalid_key_format"}), 400

    if not validation.get("valid"):
        return jsonify({
            "error": validation.get("reason"),
            "validation": validation,
        }), 403

    result = send_likes_to_uid(uid, region)

    log_action(me["name"], "like", uid=uid, region=region,
               nickname=result.get("nickname"),
               before=result.get("before"), after=result.get("after"),
               added=result.get("added"),
               tokens_used=result.get("tokens_used"),
               status=result.get("status"),
               limit=validation.get("limit"),
               remaining=validation.get("remaining"),
               key_type=key_type,
               error=result.get("error"))

    result["key_info"] = validation
    return jsonify(result), (200 if not result.get("error") else 500)

@app.route("/admin/bots/broadcast", methods=["POST"])
@admin_required                                          # 🔥 owner → admin
def admin_broadcast_custom():
    from logs import send_telegram_log, send_discord_log
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"error": "message required"}), 400

    if len(message) > 2000:
        return jsonify({"error": "message too long (max 2000)"}), 400

    me = current_user()
    header = f"📢 BROADCAST — from {me['name']} ({me.get('role', 'user')})\n{'─' * 24}\n"
    full = header + message

    tg = send_telegram_log(full)
    dc = send_discord_log(full)

    log_action(me["name"], "broadcast",
               message_len=len(message), telegram=tg, discord=dc)

    return jsonify({"ok": True, "telegram": tg, "discord": dc})

@app.route("/admin/users/<name>", methods=["DELETE"])
@admin_required
def admin_delete_user(name):
    me = current_user()
    result = delete_user(name, by_role=me.get("role"))
    if not result.get("ok"):
        return jsonify({"error": result.get("reason")}), 400
    log_action(me["name"], "user_delete", target=name)
    return jsonify({"ok": True}), 200


@app.route("/admin/users/<name>/status", methods=["POST"])
@admin_required
def admin_user_status(name):
    data = request.get_json(silent=True) or request.form
    status = data.get("status")
    me = current_user()
    result = set_user_status(name, status, by_role=me.get("role"))
    if not result.get("ok"):
        return jsonify({"error": result.get("reason")}), 400
    log_action(me["name"], "user_status", target=name, status=status)
    return jsonify({"ok": True}), 200


# ============================================================
# ADMIN — API keys
# ============================================================
@app.route("/admin/keys/api/generate", methods=["POST"])
@admin_required
def admin_gen_api_key():
    data = request.get_json(silent=True) or request.form
    credits = data.get("credits_per_day")
    duration = int(data.get("duration_days") or 30)
    region = (data.get("region") or "ALL").upper()
    admin_key = bool(data.get("admin_key", False))

    me = current_user()
    
    # 🔥 SECURITY: Only owner can generate FF-AD keys
    if admin_key and me.get("role") != "owner":
        return jsonify({"error": "forbidden",
                        "message": "Only owner can generate admin keys."}), 403
    
    try:
        credits = int(credits) if credits not in (None, "", "null") else None
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_credits"}), 400

    if region not in ("ALL", "AG", "IND", "NX"):
        return jsonify({"error": "invalid_region"}), 400

    try:
        key = generate_api_key(
            credits_per_day=credits,
            duration_days=duration,
            region=region,
            created_by=me["name"],
            admin=admin_key,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    log_action(me["name"], "key_generate", key=key, key_type="api",
               credits=credits, days=duration, region=region, admin=admin_key)
    return jsonify({
        "ok": True, "key": key, "region": region,
        "type": "unlimited" if credits is None else "credits",
    })


@app.route("/admin/keys/api", methods=["GET"])
@admin_required
def admin_list_api_keys():
    return jsonify({"keys": list_all_api_keys(), "counts": count_active_keys()})


@app.route("/admin/keys/api/<key>", methods=["DELETE"])
@admin_required
def admin_delete_api_key(key):
    me = current_user()
    doc = api_keys_col.find_one({"key": key})
    if not doc:
        return jsonify({"error": "not_found"}), 404
    
    # 🔥 SECURITY: Admin cannot delete FF-AD keys
    if doc.get("is_admin_key") and me.get("role") != "owner":
        return jsonify({"error": "forbidden",
                        "message": "Only owner can delete admin keys."}), 403
    
    if delete_api_key(key):
        log_action(me["name"], "key_delete", key=key, key_type="api")
        return jsonify({"ok": True})
    return jsonify({"error": "not_found"}), 404


# ============================================================
# ADMIN — Like keys
# ============================================================
@app.route("/admin/keys/like/generate", methods=["POST"])
@admin_required
def admin_gen_like_key():
    data = request.get_json(silent=True) or request.form
    per_uid = int(data.get("per_uid_per_day") or 5)
    duration = int(data.get("duration_days") or 30)

    me = current_user()
    key = generate_like_key(per_uid_per_day=per_uid,
                            duration_days=duration,
                            created_by=me["name"])
    log_action(me["name"], "key_generate", key=key, key_type="like",
               per_uid=per_uid, days=duration)
    return jsonify({"ok": True, "key": key}), 200


@app.route("/admin/keys/like", methods=["GET"])
@admin_required
def admin_list_like_keys():
    return jsonify({"keys": list_all_like_keys(), "counts": count_active_like_keys()})


@app.route("/admin/keys/like/<key>", methods=["DELETE"])
@admin_required
def admin_delete_like_key(key):
    if delete_like_key(key):
        log_action(current_user()["name"], "key_delete", key=key, key_type="like")
        return jsonify({"ok": True})
    return jsonify({"error": "not_found"}), 404


# ============================================================
# ADMIN — Boost
# ============================================================
@app.route("/admin/boost/create", methods=["POST"])
@admin_required
def admin_boost_create():
    data = request.get_json(silent=True) or request.form
    uid = str(data.get("uid") or "").strip()
    add_likes = int(data.get("add_likes") or data.get("target_likes") or 0)   # 🔥 accept both
    per_day = int(data.get("per_day") or 200)
    region = (data.get("region") or "AG").upper()

    if not uid or add_likes <= 0:
        return jsonify({"error": "uid and add_likes required"}), 400

    me = current_user()
    result = create_boost_job(uid, add_likes, per_day, region, me["name"])
    if not result.get("ok"):
        return jsonify({"error": result.get("reason"), **result}), 400
    return jsonify({"ok": True, **result})


@app.route("/admin/boost", methods=["GET"])
@admin_required
def admin_boost_list():
    return jsonify({"jobs": list_boost_jobs()})


@app.route("/admin/boost/<uid>", methods=["DELETE"])
@admin_required
def admin_boost_delete(uid):
    if delete_boost_job(uid):
        log_action(current_user()["name"], "boost_delete", uid=uid)
        return jsonify({"ok": True})
    return jsonify({"error": "not_found"}), 404


@app.route("/admin/boost/<uid>/pause", methods=["POST"])
@admin_required
def admin_boost_pause(uid):
    return jsonify({"ok": pause_boost_job(uid)})


@app.route("/admin/boost/<uid>/resume", methods=["POST"])
@admin_required
def admin_boost_resume(uid):
    return jsonify({"ok": resume_boost_job(uid)})


# ============================================================
# ADMIN — Auto
# ============================================================
@app.route("/admin/auto/create", methods=["POST"])
@admin_required
def admin_auto_create():
    data = request.get_json(silent=True) or request.form
    uid = str(data.get("uid") or "").strip()
    per_day = int(data.get("per_day") or 200)
    days = int(data.get("duration_days") or 30)
    region = (data.get("region") or "AG").upper()

    if not uid or per_day <= 0 or days <= 0:
        return jsonify({"error": "uid, per_day, duration_days required"}), 400

    me = current_user()
    result = create_auto_job(uid, per_day, days, region, me["name"])
    if not result.get("ok"):
        return jsonify({"error": result.get("reason"), **result}), 400
    return jsonify({"ok": True, **result})


@app.route("/admin/auto", methods=["GET"])
@admin_required
def admin_auto_list():
    return jsonify({"jobs": list_auto_jobs()})


@app.route("/admin/auto/<uid>", methods=["DELETE"])
@admin_required
def admin_auto_delete(uid):
    if delete_auto_job(uid):
        log_action(current_user()["name"], "auto_delete", uid=uid)
        return jsonify({"ok": True})
    return jsonify({"error": "not_found"}), 404


@app.route("/admin/auto/<uid>/pause", methods=["POST"])
@admin_required
def admin_auto_pause(uid):
    return jsonify({"ok": pause_auto_job(uid)})


@app.route("/admin/auto/<uid>/resume", methods=["POST"])
@admin_required
def admin_auto_resume(uid):
    return jsonify({"ok": resume_auto_job(uid)})


# ============================================================
# ADMIN — Stats / Logs
# ============================================================
@app.route("/admin/stats", methods=["GET"])
@admin_required
def admin_stats():
    return jsonify({
        "api_keys": count_active_keys(),
        "like_keys": count_active_like_keys(),
        "boost_active": __import__("db").boost_like_col.count_documents({"status": "active"}),
        "auto_active": __import__("db").auto_like_col.count_documents({"status": "active"}),
        "accounts": accounts_col.count_documents({}),
        "activity": get_stats_today(),
    })


@app.route("/admin/logs", methods=["GET"])
@admin_required
def admin_logs():
    limit = int(request.args.get("limit", 100))
    user = request.args.get("user")
    action = request.args.get("action")

    query = {}
    if user:
        query["user"] = user
    else:
        # Exclude client (role=user) logs — those are personal to client panel
        from db import accounts_col
        client_names = [
            a["name"] for a in
            accounts_col.find({"role": "user"}, {"name": 1, "_id": 0})
        ]
        query["user"] = {"$nin": client_names}

    if action:
        query["action"] = action

    cursor = activity_logs_col.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit)
    logs = [_stringify_doc(d) for d in cursor]
    return jsonify({"logs": logs})

# ============================================================
# ADMIN — Scheduler Control
# ============================================================
@app.route("/admin/scheduler/status", methods=["GET"])
@admin_required
def admin_scheduler_status():
    from datetime import timezone as tz
    jobs = []
    for job in scheduler.get_jobs():
        nxt = job.next_run_time
        if nxt:
            # Force UTC display
            nxt = nxt.astimezone(tz.utc)
        jobs.append({
            "id": job.id,
            "next_run": nxt.isoformat() if nxt else None,
        })
    return jsonify({
        "running": scheduler.running,
        "timezone": "UTC",
        "jobs": jobs,
    })


@app.route("/admin/scheduler/run-daily", methods=["POST"])
@owner_required
def admin_scheduler_run_daily():
    """Owner-only: manually trigger daily job (for testing)."""
    _daily_job()
    return jsonify({"ok": True, "message": "Daily job executed"})

# ============================================================
# ADMIN — Bot Settings / Test
# ============================================================
@app.route("/admin/bots/settings", methods=["GET"])
@admin_required
def admin_bot_settings():
    from logs import list_bot_settings, mask_value
    s = list_bot_settings()
    for k in list(s.keys()):
        s[k] = mask_value(k, s[k])
    return jsonify({"settings": s})


@app.route("/admin/bots/test", methods=["POST"])
@owner_required
def admin_bot_test():
    """Send a test message to both platforms."""
    from logs import broadcast_log
    result = broadcast_log({
        "timestamp": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).replace(tzinfo=None),
        "user": "system",
        "action": "bot_test",
        "status": "ok",
        "reason": "Manual test from admin panel",
    })
    return jsonify({"ok": True, "result": result})


# ============================================================
# CLIENT — Self-service
# ============================================================
@app.route("/client/me", methods=["GET"])
@login_required
def client_me():
    user = current_user()
    api_key_doc = None
    like_key_doc = None
    like_usage = []

    if user.get("assigned_api_key"):
        api_key_doc = api_keys_col.find_one(
            {"key": user["assigned_api_key"]},
            {"_id": 0, "assigned_to": 0},
        )
    if user.get("assigned_like_key"):
        like_key_doc = like_keys_col.find_one(
            {"key": user["assigned_like_key"]},
            {"_id": 0, "assigned_to": 0},
        )
        like_usage = get_like_usage_summary(user["assigned_like_key"])

    return jsonify({
        "user": {"name": user["name"], "role": user.get("role"),
                 "status": user.get("status")},
        "api_key": _stringify_doc(api_key_doc) if api_key_doc else None,
        "like_key": _stringify_doc(like_key_doc) if like_key_doc else None,
        "like_usage": like_usage,
    })

# ============================================================
# CLIENT — Like Endpoint (self-service)
# ============================================================
@app.route("/client/like", methods=["POST"])
@login_required
def client_like():
    user = current_user()
    data = request.get_json(silent=True) or {}
    uid = str(data.get("uid", "")).strip()
    region = (data.get("region") or "").upper()

    if not uid or not region:
        return jsonify({"error": "uid and region required"}), 400

    # Get client's key
    key = user.get("assigned_like_key") or user.get("assigned_api_key")
    if not key:
        return jsonify({"error": "no_key_assigned"}), 400

    # Validate
    if key.startswith(LIKE_KEY_PREFIX):
        validation = validate_like_call(key, uid)
    else:
        validation = validate_api_call(key, resolve_region(region))

    if not validation.get("valid"):
        return jsonify({"error": validation.get("reason"),
                        "validation": validation}), 403

    result = send_likes_to_uid(uid, region)

    log_event(user["name"], "like", uid=uid, region=region,
              nickname=result.get("nickname"),
              before=result.get("before"), after=result.get("after"),
              added=result.get("added"),
              tokens_used=result.get("tokens_used"),
              status=result.get("status"),
              limit=validation.get("limit"), remaining=validation.get("remaining"),
              broadcast=False)   # 🔥 client log — no bot

    result["key_info"] = validation
    return jsonify(result)

# ============================================================
# CLIENT — Boost Create Endpoint (self-service)
# ============================================================
@app.route("/client/boost/create", methods=["POST"])
@login_required
def client_boost_create():
    user = current_user()
    data = request.get_json(silent=True) or {}
    uid = str(data.get("uid", "")).strip()
    region = (data.get("region") or "AG").upper()
    add_likes = int(data.get("add_likes") or data.get("target_likes") or 0)

    if not uid or add_likes <= 0:
        return jsonify({"error": "uid and add_likes required"}), 400

    # 🔥 Get client's key
    key = user.get("assigned_api_key") or user.get("assigned_like_key")
    if not key:
        return jsonify({"error": "no_key_assigned"}), 400

    # 🔥 CRITICAL FIX — Like key CANNOT create boost job
    if key.startswith(LIKE_KEY_PREFIX):
        return jsonify({
            "error": "like_key_cannot_create_job",
            "message": "Like keys (FF-LK) can only send manual likes. "
                       "Boost jobs require an API key (FF-API).",
        }), 403

    # Validate API key (FF-API or FF-AD)
    if key.startswith(API_KEY_PREFIX) or key.startswith(ADMIN_KEY_PREFIX):
        validation = validate_api_call(key, resolve_region(region))
        if not validation.get("valid"):
            return jsonify({"error": validation.get("reason")}), 403

    result = create_boost_job(uid, add_likes, 200, region, user["name"])
    if not result.get("ok"):
        return jsonify({"error": result.get("reason"), **result}), 400
    return jsonify({"ok": True, **result})
# ============================================================
# CLIENT — Auto Create Endpoint (self-service)
# ============================================================
@app.route("/client/auto/create", methods=["POST"])
@login_required
def client_auto_create():
    user = current_user()
    data = request.get_json(silent=True) or {}
    uid = str(data.get("uid", "")).strip()
    region = (data.get("region") or "AG").upper()
    days = int(data.get("duration_days") or 0)

    if not uid or days <= 0:
        return jsonify({"error": "uid and duration_days required"}), 400

    # 🔥 Get client's key
    key = user.get("assigned_api_key") or user.get("assigned_like_key")
    if not key:
        return jsonify({"error": "no_key_assigned"}), 400

    # 🔥 CRITICAL FIX — Like key CANNOT create auto job
    if key.startswith(LIKE_KEY_PREFIX):
        return jsonify({
            "error": "like_key_cannot_create_job",
            "message": "Like keys (FF-LK) can only send manual likes. "
                       "Auto jobs require an API key (FF-API).",
        }), 403

    # Check duration vs key expiry
    key_doc = api_keys_col.find_one({"key": key})
    if not key_doc:
        return jsonify({"error": "key_not_found"}), 400

    exp = key_doc.get("expires_at")
    if exp:
        remaining_days = (exp - datetime.now(timezone.utc).replace(tzinfo=None)).days
        if days > remaining_days:
            return jsonify({
                "error": "duration_exceeds_key",
                "message": f"Duration exceeds key expiry. Max allowed: {remaining_days} days.",
                "max_days": remaining_days,
            }), 400

    result = create_auto_job(uid, 200, days, region, user["name"])
    if not result.get("ok"):
        return jsonify({"error": result.get("reason")}), 400
    return jsonify({"ok": True, **result})

# ============================================================
# CLIENT — Jobs List Endpoint (self-service)
# ============================================================
@app.route("/client/jobs", methods=["GET"])
@login_required
def client_jobs():
    user = current_user()
    boost = list(boost_like_col.find(
        {"created_by": user["name"]},
        {"_id": 0}
    ).sort("created_at", -1))
    auto = list(auto_like_col.find(
        {"created_by": user["name"]},
        {"_id": 0}
    ).sort("created_at", -1))
    return jsonify({
        "boost": [_stringify_doc(b) for b in boost],
        "auto": [_stringify_doc(a) for a in auto],
    })

@app.route("/client/job/<job_type>/<uid>", methods=["DELETE"])
@login_required
def client_delete_job(job_type, uid):
    user = current_user()
    if job_type == "boost":
        r = boost_like_col.delete_one({"uid": uid, "created_by": user["name"]})
    elif job_type == "auto":
        r = auto_like_col.delete_one({"uid": uid, "created_by": user["name"]})
    else:
        return jsonify({"error": "invalid_job_type"}), 400

    if r.deleted_count == 0:
        return jsonify({"error": "not_found_or_not_owner"}), 404

    log_action(user["name"], f"{job_type}_delete", uid=uid, broadcast=False)
    return jsonify({"ok": True})

# ============================================================
# CLIENT — Logs (self-service)
# ============================================================
@app.route("/client/logs", methods=["GET"])
@login_required
def client_logs():
    user = current_user()
    limit = int(request.args.get("limit", 50))
    # 🔥 Filter by user only (already does, but double-check)
    logs = get_recent_logs(limit=limit, user=user["name"])
    return jsonify({"logs": logs})


@app.route("/admin/scheduler/run-cleanup", methods=["POST"])
@owner_required
def admin_scheduler_run_cleanup():
    """Owner-only: manually trigger cleanup (for testing)."""
    _cleanup_job()
    return jsonify({"ok": True, "message": "Cleanup executed"})

@app.route("/admin/scheduler/run-init", methods=["POST"])
@owner_required
def admin_scheduler_run_init():
    """Owner-only: manually trigger pending job init."""
    _init_pending_jobs()
    return jsonify({"ok": True, "message": "Pending jobs initialized"})

# ============================================================
# HELPERS
# ============================================================
def _stringify_doc(doc):
    if not doc:
        return None
    from datetime import datetime
    out = {}
    for k, v in doc.items():
        out[k] = v.isoformat() if isinstance(v, datetime) else v
    return out

# ============================================================
# SCHEDULER — APScheduler
# ============================================================
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from subscriptionAPI import (
    reset_daily_credits, remove_expired_keys,
    run_boost_jobs, run_auto_jobs, check_token_pool,
)
from subscription import (
    reset_daily_like_usage, remove_expired_like_keys,
)


def _daily_job():
    """Runs at 12:00 AM UTC — token check, boost/auto, credits reset."""
    print("\n[SCHEDULER] Daily job starting…")
    try:
        # ============ STEP 1: TOKEN POOL CHECK ============
        print("[SCHEDULER] Checking token pools…")
        for region in ["AG", "IND", "NX"]:
            try:
                status = check_token_pool(region, sample_size=10)
                print(f"  • {region} tokens: {status['valid']}/{status['sampled']} valid "
                      f"(total {status['total']})")
                if status.get("needs_refresh"):
                    print(f"  ⚠️  {region} pool needs refresh")
                    # Trigger refresh — inline call
                    try:
                        import asyncio
                        from tokens_handler import refresh_tokens, move_tokens
                        asyncio.run(refresh_tokens(region))
                        asyncio.run(move_tokens(region, merge=True))
                        print(f"  ✅ {region} refreshed")
                    except Exception as e:
                        print(f"  ❌ {region} refresh failed: {e}")
            except Exception as e:
                print(f"  ❌ {region} check failed: {e}")

        # ============ STEP 2: CREDITS + USAGE RESET ============
        n1 = reset_daily_credits()
        n2 = reset_daily_like_usage()
        print(f"  • Credits reset:       {n1} keys")
        print(f"  • Like usage cleaned:  {n2} records")

        # ============ STEP 3: RUN BOOST JOBS ============
        boost_summary = run_boost_jobs()
        print(f"  • Boost jobs:          {boost_summary['processed']} processed, "
              f"{boost_summary['initialized']} initialized, "
              f"{boost_summary['completed']} completed, "
              f"{boost_summary['failed']} failed, "
              f"{boost_summary['terminated']} terminated")

        # ============ STEP 4: RUN AUTO JOBS ============
        auto_summary = run_auto_jobs()
        print(f"  • Auto jobs:           {auto_summary['processed']} processed, "
              f"{auto_summary['initialized']} initialized, "
              f"{auto_summary['expired']} expired, "
              f"{auto_summary['failed']} failed")

    except Exception as e:
        print(f"[SCHEDULER] Daily job error: {e}")
        import traceback
        traceback.print_exc()
    print("[SCHEDULER] Daily job done.\n")


def _cleanup_job():
    """Runs every 5 min — real-time expired key cleanup."""
    try:
        n1 = remove_expired_keys()
        n2 = remove_expired_like_keys()
        if n1 or n2:
            print(f"[CLEANUP] Removed {n1} API keys, {n2} Like keys.")
    except Exception as e:
        print(f"[CLEANUP] Error: {e}")


scheduler = BackgroundScheduler(timezone="UTC")


def start_scheduler():
    scheduler.add_job(
        _daily_job,
        CronTrigger(hour=0, minute=0, timezone="UTC"),
        id="daily_job",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        _cleanup_job,
        IntervalTrigger(minutes=5),
        id="cleanup_job",
        replace_existing=True,
        misfire_grace_time=60,
    )
    scheduler.start()
    print("[SCHEDULER] Started — daily at 00:00 UTC, cleanup every 5 min.")

def start_scheduler():
    # Daily job (00:00 UTC)
    scheduler.add_job(
        _daily_job,
        CronTrigger(hour=0, minute=0, timezone="UTC"),
        id="daily_job",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Cleanup job (every 5 min)
    scheduler.add_job(
        _cleanup_job,
        IntervalTrigger(minutes=5),
        id="cleanup_job",
        replace_existing=True,
        misfire_grace_time=60,
    )

    # 🔥 NEW: Pending jobs init (every 15 min)
    scheduler.add_job(
        _init_pending_jobs,
        IntervalTrigger(minutes=15),
        id="init_pending_jobs",
        replace_existing=True,
        misfire_grace_time=120,
    )

    scheduler.start()
    print("[SCHEDULER] Started — daily at 00:00 UTC, cleanup every 5 min, init pending every 15 min.")


def _init_pending_jobs():
    """Runs every 15 min — initializes pending jobs."""
    try:
        from subscriptionAPI import initialize_pending_jobs
        result = initialize_pending_jobs()
        if result["boost_init"] or result["auto_init"]:
            print(f"[INIT] Boost: {result['boost_init']} · Auto: {result['auto_init']}")
    except Exception as e:
        print(f"[INIT] Error: {e}")

# ============================================================
# TOKEN MANAGER (background)
# ============================================================
def start_background_tokens():
    thread = threading.Thread(
        target=lambda: asyncio.run(start_token_manager()),
        daemon=True,
    )
    thread.start()


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    start_background_tokens()
    start_scheduler()
    start_bots()                    # 🔥 NEW
    app.run(host="0.0.0.0", port=PORT, debug=False)