"""
logs.py
-------
Activity logging + Telegram/Discord bot (log display only).
Commands: /start, /setlogs, /setbostlog, /setautolog, /removelog
"""
import time
import threading
import requests
from datetime import datetime, timezone

from config import (
    TELEGRAM_BOT_TOKEN as ENV_TG_TOKEN,
    DISCORD_BOT_TOKEN as ENV_DC_TOKEN,
    TELEGRAM_OWNER_IDS as ENV_TG_OWNERS,
    DISCORD_OWNER_IDS as ENV_DC_OWNERS,
)
from db import activity_logs_col, bot_settings_col


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ============================================================
# SECTION 1 — ACTIVITY LOGGING
# ============================================================
def log_action(user, action, **details):
    activity_logs_col.insert_one({
        "timestamp": _now(),
        "user": user or "system",
        "action": action,
        **details,
    })


def get_recent_logs(limit=100, user=None, action=None):
    q = {}
    if user: q["user"] = user
    if action: q["action"] = action
    cursor = activity_logs_col.find(q, {"_id": 0}).sort("timestamp", -1).limit(limit)
    return [_stringify(d) for d in cursor]


def get_stats_today():
    start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )
    return {
        "likes_today":   activity_logs_col.count_documents(
            {"action": "like", "timestamp": {"$gte": start}}),
        "success_today": activity_logs_col.count_documents(
            {"action": "like", "status": 1, "timestamp": {"$gte": start}}),
        "total_logs":    activity_logs_col.count_documents({}),
    }


def _stringify(doc):
    out = {}
    for k, v in doc.items():
        out[k] = v.isoformat() if isinstance(v, datetime) else v
    return out


# ============================================================
# SECTION 2 — BOT SETTINGS
# ============================================================
_ALLOWED_KEYS = {
    "telegram_bot_token",
    "telegram_all_logs", "telegram_boost_logs", "telegram_auto_logs",
    "discord_bot_token",
    "discord_all_logs", "discord_boost_logs", "discord_auto_logs",
}

_ENV_FALLBACK = {
    "telegram_bot_token": ENV_TG_TOKEN,
    "discord_bot_token":  ENV_DC_TOKEN,
}


def get_bot_setting(key):
    doc = bot_settings_col.find_one({"key": key})
    if doc and doc.get("value"):
        return str(doc["value"])
    return _ENV_FALLBACK.get(key, "")


def set_bot_setting(key, value):
    if key not in _ALLOWED_KEYS:
        raise ValueError(f"Unknown key: {key}")
    bot_settings_col.update_one(
        {"key": key},
        {"$set": {"key": key, "value": str(value), "updated_at": _now()}},
        upsert=True,
    )


# 🔥 NEW — for /admin/bots/settings route
def list_bot_settings():
    """Reads DB, but falls back to env if empty."""
    out = {}
    for key in _ALLOWED_KEYS:
        out[key] = get_bot_setting(key)     # env fallback thake
    return out


# 🔥 NEW — for masked display
def mask_value(key, value):
    if not value:
        return "(empty)"
    if "token" in key:
        return value[:8] + "…" + value[-4:] if len(value) > 15 else value
    if "id" in key and len(value) > 12:
        return value[:8] + "…" + value[-4:]
    return value


# ---------- LOG TARGETS (REPLACE — one per type) ----------
def get_log_targets(platform, log_type):
    """platform: telegram | discord. log_type: all | boost | auto"""
    key = f"{platform}_{log_type}_logs"
    val = get_bot_setting(key)
    if not val:
        return []
    return [val.strip()]     # single target


def set_log_target(platform, log_type, chat_id):
    """🔥 REPLACE target for this log type (not append)."""
    key = f"{platform}_{log_type}_logs"
    set_bot_setting(key, str(chat_id))
    return str(chat_id)


def remove_log_targets(platform, chat_id):
    """Remove chat_id from all log-type targets where it matches."""
    cid = str(chat_id)
    removed = []
    for log_type in ("all", "boost", "auto"):
        key = f"{platform}_{log_type}_logs"
        if get_bot_setting(key) == cid:      # equality — single value
            set_bot_setting(key, "")
            removed.append(log_type)
    return removed


def remove_log_targets(platform, chat_id):
    """Remove chat_id from all log-type targets. Returns removed types."""
    cid = str(chat_id)
    removed = []
    for log_type in ("all", "boost", "auto"):
        key = f"{platform}_{log_type}_logs"
        current = get_log_targets(platform, log_type)
        if cid in current:
            current.remove(cid)
            set_bot_setting(key, ",".join(current))
            removed.append(log_type)
    return removed


# ============================================================
# SECTION 3 — OWNER VERIFICATION
# ============================================================
def _parse_ids(s):
    if not s:
        return set()
    return {x.strip() for x in str(s).split(",") if x.strip()}


def is_telegram_owner(user_id):
    ids = _parse_ids(ENV_TG_OWNERS)
    if not ids:
        return True   # no env set → allow (dev mode)
    return str(user_id) in ids


def is_discord_owner(user_id):
    ids = _parse_ids(ENV_DC_OWNERS)
    if not ids:
        return True
    return str(user_id) in ids


# ============================================================
# SECTION 4 — LOG FORMATTERS
# ============================================================
REGION_NAMES = {
    "BD": "Bangladesh", "PK": "Pakistan", "IN": "India", "BR": "Brazil",
    "US": "United States", "ID": "Indonesia", "TH": "Thailand", "VN": "Vietnam",
    "MY": "Malaysia", "PH": "Philippines", "SG": "Singapore", "MX": "Mexico",
    "SA": "Saudi Arabia", "AE": "UAE", "EG": "Egypt", "RU": "Russia",
    "TR": "Turkey", "NG": "Nigeria", "ZA": "South Africa", "AR": "Argentina",
    "CO": "Colombia", "PE": "Peru", "CL": "Chile", "CA": "Canada",
    "GB": "United Kingdom", "DE": "Germany", "FR": "France", "ES": "Spain",
    "IT": "Italy", "JP": "Japan", "KR": "Korea", "TW": "Taiwan",
    "HK": "Hong Kong", "NP": "Nepal", "LK": "Sri Lanka", "AF": "Afghanistan",
    "KH": "Cambodia", "MM": "Myanmar", "LA": "Laos",
}


def _region_name(code):
    if not code:
        return "Unknown"
    return REGION_NAMES.get(str(code).upper(), str(code))


def _time_label(dt):
    if not dt:
        return "—"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return dt
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        if dt.date() == now.date():
            return f"Today at {dt.strftime('%H:%M')}"
    except Exception:
        pass
    return dt.strftime("%d/%m/%Y %H:%M")


def _format_like(entry):
    remaining = entry.get("remaining")
    limit = entry.get("limit")
    if limit is None:
        req_line = "Requests remaining: Unlimited"
    else:
        req_line = f"Requests remaining: {remaining}/{limit}"
    return "\n".join([
        "✔️ FF LIKE",
        "─" * 24,
        f"Nickname: {entry.get('nickname', '—')}",
        f"Region: {_region_name(entry.get('region'))}",
        f"Player UID: {entry.get('uid', '—')}",
        f"Like before: {entry.get('before', '—')}",
        f"Like added : +{entry.get('added', 0)}",
        f"Like after: {entry.get('after', '—')}",
        f"Tokens used: {entry.get('tokens_used', 0)}",
        req_line,
        "─" * 24,
        _time_label(entry.get("timestamp")),
    ])


def _format_boost(entry):
    start = entry.get("start_likes") or 0
    after = entry.get("after") or 0
    target = entry.get("target") or 0
    pct = ""
    if target > start:
        try:
            pct = f" ({(after - start) / (target - start) * 100:.2f}%)"
        except Exception:
            pct = ""
    total_add = target - start
    return "\n".join([
        "🔥 FF BOOST LIKE",
        "─" * 24,
        f"(Added by: {entry.get('added_by', 'system')})",
        f"Nickname: {entry.get('nickname', '—')}",
        f"Player UID: {entry.get('uid', '—')}",
        f"Region: {_region_name(entry.get('region'))}",
        f"Like start: {start}",
        f"Like before: {entry.get('before', '—')}",
        f"Like added: +{entry.get('added', 0)}",
        f"Like after: {after}{pct}",
        f"Tokens used: {entry.get('tokens_used', 0)}",
        f"Target: {target} (added: +{total_add})",
        "─" * 24,
        _time_label(entry.get("timestamp")),
    ])


def _format_auto(entry):
    exp = entry.get("expires_at")
    if isinstance(exp, str):
        try:
            exp = datetime.fromisoformat(exp)
        except Exception:
            pass
    if isinstance(exp, datetime):
        exp_line = exp.strftime("%d/%m/%Y")
    else:
        exp_line = exp or "—"
    return "\n".join([
        "🔁 FF AUTO LIKE",
        "─" * 24,
        f"(Added by: {entry.get('added_by', 'system')})",
        f"Nickname: {entry.get('nickname', '—')}",
        f"Region: {_region_name(entry.get('region'))}",
        f"Player UID: {entry.get('uid', '—')}",
        f"Like before: {entry.get('before', '—')}",
        f"Like added : +{entry.get('added', 0)}",
        f"Like after: {entry.get('after', '—')}",
        f"Tokens used: {entry.get('tokens_used', 0)}",
        f"Expires at: {exp_line}",
        "─" * 24,
        _time_label(entry.get("timestamp")),
    ])


def _format_generic(entry):
    lines = ["🔥 FF LIKE API", "─" * 24,
             f"📌 {entry.get('action', 'event')}"]
    for k, v in entry.items():
        if k in ("timestamp", "action") or v is None:
            continue
        lines.append(f"• {k}: {v}")
    lines.append("─" * 24)
    lines.append(_time_label(entry.get("timestamp")))
    return "\n".join(lines)


def format_log(entry):
    action = entry.get("action", "")
    if action == "like":
        return _format_like(entry)
    if action in ("boost_run", "boost_complete", "boost_create"):
        return _format_boost(entry)
    if action in ("auto_run", "auto_create"):
        return _format_auto(entry)
    return _format_generic(entry)


# ============================================================
# SECTION 5 — SEND
# ============================================================
def _send_telegram_to(chat_id, text):
    token = get_bot_setting("telegram_bot_token")
    if not token:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text,
                  "disable_web_page_preview": True},
            timeout=10,
        )
        return r.ok
    except Exception as e:
        print(f"[TG] send err: {e}")
        return False


def _send_discord_to(channel_id, text):
    token = get_bot_setting("discord_bot_token")
    if not token:
        return False
    try:
        r = requests.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers={
                "Authorization": f"Bot {token}",
                "Content-Type": "application/json",
            },
            json={"content": text[:1900]},
            timeout=10,
        )
        if not r.ok:
            print(f"[DC] send failed: {r.status_code} {r.text[:120]}")
        return r.ok
    except Exception as e:
        print(f"[DC] send err: {e}")
        return False

def send_telegram_log(text):
    """Public — send to all configured Telegram targets."""
    targets = set()
    targets.update(get_log_targets("telegram", "all"))
    targets.update(get_log_targets("telegram", "boost"))
    targets.update(get_log_targets("telegram", "auto"))
    if not targets:
        return False
    return any(_send_telegram_to(c, text) for c in targets)


def send_discord_log(text):
    """Public — send to all configured Discord targets."""
    targets = set()
    targets.update(get_log_targets("discord", "all"))
    targets.update(get_log_targets("discord", "boost"))
    targets.update(get_log_targets("discord", "auto"))
    if not targets:
        return False
    return any(_send_discord_to(c, text) for c in targets)

# ============================================================
# SECTION 6 — EVENT DISPATCHER
# ============================================================
BOOST_ACTIONS = {"boost_run", "boost_complete", "boost_create"}
AUTO_ACTIONS  = {"auto_run", "auto_create", "auto_expired"}
LIKE_ACTIONS  = {"like"}


def broadcast_log(entry):
    text = format_log(entry)
    action = entry.get("action", "")

    tg_targets = set()
    dc_targets = set()

    if action in LIKE_ACTIONS:
        tg_targets.update(get_log_targets("telegram", "all"))
        dc_targets.update(get_log_targets("discord", "all"))
    elif action in BOOST_ACTIONS:
        tg_targets.update(get_log_targets("telegram", "all"))
        tg_targets.update(get_log_targets("telegram", "boost"))
        dc_targets.update(get_log_targets("discord", "all"))
        dc_targets.update(get_log_targets("discord", "boost"))
    elif action in AUTO_ACTIONS:
        tg_targets.update(get_log_targets("telegram", "all"))
        tg_targets.update(get_log_targets("telegram", "auto"))
        dc_targets.update(get_log_targets("discord", "all"))
        dc_targets.update(get_log_targets("discord", "auto"))
    else:
        return {"telegram": 0, "discord": 0}

    tg_count = sum(1 for c in tg_targets if _send_telegram_to(c, text))
    dc_count = sum(1 for c in dc_targets if _send_discord_to(c, text))

    return {"telegram": tg_count, "discord": dc_count}


def log_event(user, action, broadcast=True, **details):
    """
    DB write + conditional broadcast.
    - Client (role=user) actions NEVER broadcast (only their own panel sees them).
    - Owner/Admin actions broadcast to bot logs.
    """
    entry = {"timestamp": _now(), "user": user or "system",
             "action": action, **details}
    activity_logs_col.insert_one(entry)

    if not broadcast:
        return entry

    # Check if user is client (role=user) — don't broadcast
    from db import accounts_col
    user_doc = accounts_col.find_one({"name": user}, {"role": 1})
    if user_doc and user_doc.get("role") == "user":
        return entry   # 🔥 Client logs stay in client panel only

    # Broadcast for owner/admin
    threading.Thread(target=broadcast_log,
                     args=(entry,), daemon=True).start()
    return entry


# ============================================================
# SECTION 7 — TELEGRAM BOT
# ============================================================
_tg_stop = threading.Event()
_tg_thread = None


def _tg_api(method, **kwargs):
    token = get_bot_setting("telegram_bot_token")
    if not token:
        return None
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/{method}",
            json=kwargs, timeout=35,
        )
        return r.json()
    except Exception as e:
        print(f"[TG:{method}] {e}")
        return None


def _tg_reply(chat_id, text):
    _tg_api("sendMessage", chat_id=chat_id, text=text,
            disable_web_page_preview=True)


def _tg_handle(update):
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return
    chat_id = msg.get("chat", {}).get("id")
    user_id = msg.get("from", {}).get("id")
    text = (msg.get("text") or "").strip()
    if not chat_id or not text:
        return

    cmd, _, _args = text.partition(" ")
    cmd = cmd.lower()

    # -------- /start (anyone) --------
    if cmd == "/start":
        _tg_reply(chat_id, (
            "🔥 FF LIKE API Bot\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Welcome! 👋\n\n"
            "📋 Owner commands:\n"
            "  /setlogs      — all logs to this chat\n"
            "  /setbostlog   — boost logs only\n"
            "  /setautolog   — auto logs only\n"
            "  /removelog    — remove this chat\n"
        ))
        return

    # -------- Owner-only commands --------
    if not is_telegram_owner(user_id):
        _tg_reply(chat_id, "🚫 Owner/Admin only.")
        return

    if cmd == "/setlogs":
        set_log_target("telegram", "all", chat_id)
        _tg_reply(chat_id,
                  "✅ This chat is now set for **ALL logs** "
                  "(previous channel replaced if any).")
        return

    if cmd in ("/setbostlog", "/setboostlog"):
        set_log_target("telegram", "boost", chat_id)
        _tg_reply(chat_id,
                  "✅ This chat is now set for **BOOST like** logs only "
                  "(previous channel replaced).")
        return

    if cmd == "/setautolog":
        set_log_target("telegram", "auto", chat_id)
        _tg_reply(chat_id,
                  "✅ This chat is now set for **AUTO like** logs only "
                  "(previous channel replaced).")
        return

    if cmd == "/removelog":
        removed = remove_log_targets("telegram", chat_id)
        if removed:
            _tg_reply(chat_id,
                      f"🗑 Removed this chat from: {', '.join(removed)} logs.")
        else:
            _tg_reply(chat_id, "ℹ️ This chat is not set for any logs.")
        return


def _tg_poll_loop():
    print("[TG] Poller started.")
    offset = 0
    while not _tg_stop.is_set():
        token = get_bot_setting("telegram_bot_token")
        if not token:
            time.sleep(5)
            continue
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"offset": offset, "timeout": 25,
                        "allowed_updates": '["message"]'},
                timeout=30,
            )
            data = r.json()
            if not data.get("ok"):
                time.sleep(3)
                continue
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                try:
                    _tg_handle(upd)
                except Exception as e:
                    print(f"[TG] handler: {e}")
        except Exception as e:
            print(f"[TG] poll: {e}")
            time.sleep(5)
    print("[TG] Poller stopped.")


def start_telegram_bot():
    global _tg_thread
    if _tg_thread and _tg_thread.is_alive():
        return
    _tg_stop.clear()
    _tg_thread = threading.Thread(target=_tg_poll_loop, daemon=True)
    _tg_thread.start()


def stop_telegram_bot():
    _tg_stop.set()


# ============================================================
# SECTION 8 — DISCORD BOT
# ============================================================
_dc_thread = None
_dc_bot = None


def _start_discord_thread():
    global _dc_thread, _dc_bot

    token = get_bot_setting("discord_bot_token")
    if not token:
        print("[DC] No token configured.")
        return

    try:
        import discord
        from discord.ext import commands
    except ImportError:
        print("[DC] discord.py not installed. Run: pip install discord.py")
        return

    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        print(f"[DC] Logged in as {bot.user}")
        try:
            synced = await bot.tree.sync()
            print(f"[DC] Synced {len(synced)} slash commands globally.")
        except Exception as e:
            print(f"[DC] Sync error: {e}")

    @bot.hybrid_command(name="start", description="Welcome message")
    async def dc_start(ctx):
        await ctx.send(
            "🔥 FF LIKE API Bot\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Welcome! 👋\n\n"
            "📋 Owner commands:\n"
            "  `!setlogs`      — all logs to this channel\n"
            "  `!setbostlog`   — boost logs only\n"
            "  `!setautolog`   — auto logs only\n"
            "  `!removelog`    — remove this channel\n"
        )

    @bot.hybrid_command(name="setlogs",
                        description="Set this channel for ALL logs")
    async def dc_setlogs(ctx):
        if not is_discord_owner(ctx.author.id):
            await ctx.send("🚫 Owner/Admin only.")
            return
        set_log_target("discord", "all", ctx.channel.id)
        await ctx.send("✅ This channel is now set for **ALL logs** "
                       "(previous channel replaced if any).")

    @bot.hybrid_command(name="setbostlog",
                        description="Set this channel for BOOST logs only")
    async def dc_setbostlog(ctx):
        if not is_discord_owner(ctx.author.id):
            await ctx.send("🚫 Owner/Admin only.")
            return
        set_log_target("discord", "boost", ctx.channel.id)
        await ctx.send("✅ This channel is now set for **BOOST like** logs only "
                       "(previous channel replaced).")

    @bot.hybrid_command(name="setboostlog",
                        description="Alias of setbostlog")
    async def dc_setboostlog(ctx):
        if not is_discord_owner(ctx.author.id):
            await ctx.send("🚫 Owner/Admin only.")
            return
        set_log_target("discord", "boost", ctx.channel.id)
        await ctx.send("✅ This channel is now set for **BOOST like** logs only "
                       "(previous channel replaced).")

    @bot.hybrid_command(name="setautolog",
                        description="Set this channel for AUTO logs only")
    async def dc_setautolog(ctx):
        if not is_discord_owner(ctx.author.id):
            await ctx.send("🚫 Owner/Admin only.")
            return
        set_log_target("discord", "auto", ctx.channel.id)
        await ctx.send("✅ This channel is now set for **AUTO like** logs only "
                       "(previous channel replaced).")

    @bot.hybrid_command(name="removelog",
                        description="Remove this channel from logs")
    async def dc_removelog(ctx):
        if not is_discord_owner(ctx.author.id):
            await ctx.send("🚫 Owner/Admin only.")
            return
        removed = remove_log_targets("discord", ctx.channel.id)
        if removed:
            await ctx.send(f"🗑 Removed this channel from: {', '.join(removed)} logs.")
        else:
            await ctx.send("ℹ️ This channel is not set for any logs.")

    def _run():
        try:
            bot.run(token)
        except Exception as e:
            print(f"[DC] thread error: {e}")

    _dc_bot = bot
    _dc_thread = threading.Thread(target=_run, daemon=True)
    _dc_thread.start()
    print("[DC] Bot thread started.")


def start_discord_bot():
    if _dc_thread and _dc_thread.is_alive():
        return
    _start_discord_thread()


# ============================================================
# SECTION 9 — STARTUP
# ============================================================
def start_bots():
    if get_bot_setting("telegram_bot_token"):
        start_telegram_bot()
    else:
        print("[TG] No token — not started.")

    if get_bot_setting("discord_bot_token"):
        start_discord_bot()
    else:
        print("[DC] No token — not started.")

    print("[BOTS] Ready.")