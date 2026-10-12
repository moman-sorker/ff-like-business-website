"""
db.py
-----
Shared MongoDB connection + collections + setup/seed.
Merged from: db.py + db_setup.py
"""
from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime, timezone
import hashlib

from config import (
    MONGO_URI, DB_NAME,
    OWNER_NAME, OWNER_PASSWORD, OWNER_MASTER_KEY,
)


# ============================================================
# SECTION 1 — CLIENT + COLLECTIONS
# ============================================================
client = MongoClient(MONGO_URI)
db = client[DB_NAME]

accounts_col      = db["accounts"]
api_keys_col      = db["api_keys"]
like_keys_col     = db["like_keys"]
like_usage_col    = db["like_usage"]
boost_like_col    = db["boost_like"]
auto_like_col     = db["auto_like"]
activity_logs_col = db["activity_logs"]
bot_settings_col  = db["bot_settings"]


# ============================================================
# SECTION 2 — SETUP / SEED
# ============================================================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def setup_database():
    print(f"[DB] Connected: {DB_NAME}")

    # -------------------- INDEXES --------------------
    accounts_col.create_index("name", unique=True)
    accounts_col.create_index("role")
    accounts_col.create_index("assigned_api_key", sparse=True)
    accounts_col.create_index("assigned_like_key", sparse=True)
    accounts_col.create_index("session_token", sparse=True)

    api_keys_col.create_index("key", unique=True)
    api_keys_col.create_index("assigned_to", sparse=True)
    api_keys_col.create_index("expires_at")
    api_keys_col.create_index("status")

    like_keys_col.create_index("key", unique=True)
    like_keys_col.create_index("assigned_to", sparse=True)
    like_keys_col.create_index("expires_at")
    like_keys_col.create_index("status")

    like_usage_col.create_index([("key", ASCENDING), ("date", ASCENDING)], unique=True)

    # 🔥 Compound unique — allows same UID for different owners
    boost_like_col.create_index(
        [("uid", 1), ("created_by", 1)],
        unique=True,
        name="uid_owner_unique"
    )
    boost_like_col.create_index("uid", name="uid_lookup")           # non-unique
    boost_like_col.create_index("status")
    boost_like_col.create_index("created_by")
    
    auto_like_col.create_index(
        [("uid", 1), ("created_by", 1)],
        unique=True,
        name="uid_owner_unique"
    )
    auto_like_col.create_index("uid", name="uid_lookup")            # non-unique
    auto_like_col.create_index("status")
    auto_like_col.create_index("created_by")
    auto_like_col.create_index("expires_at")

    activity_logs_col.create_index([("timestamp", DESCENDING)])
    activity_logs_col.create_index("user")
    activity_logs_col.create_index("action")

    bot_settings_col.create_index("key", unique=True)

    print("[DB] Indexes created.")

    # -------------------- SEED OWNER --------------------
    owner_doc = {
        "name": OWNER_NAME,
        "password_hash": hash_password(OWNER_PASSWORD),
        "role": "owner",
        "master_key": OWNER_MASTER_KEY,
        "assigned_api_key": None,
        "assigned_like_key": None,
        "session_token": None,
        "status": "active",
        "created_at": datetime.now(timezone.utc),
        "created_by": "system",
    }

    if accounts_col.find_one({"name": OWNER_NAME}):
        accounts_col.update_one(
            {"name": OWNER_NAME},
            {"$set": {
                "password_hash": hash_password(OWNER_PASSWORD),
                "master_key": OWNER_MASTER_KEY,
                "role": "owner",
                "status": "active",
            }},
        )
        print(f"[SEED] Owner '{OWNER_NAME}' updated.")
    else:
        accounts_col.insert_one(owner_doc)
        print(f"[SEED] Owner '{OWNER_NAME}' created.")

    # -------------------- SEED ADMIN --------------------
    if not accounts_col.find_one({"name": "admin"}):
        accounts_col.insert_one({
            "name": "admin",
            "password_hash": hash_password("admin#123"),
            "role": "admin",
            "master_key": None,
            "assigned_api_key": None,
            "assigned_like_key": None,
            "session_token": None,
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "created_by": OWNER_NAME,
        })
        print("[SEED] Default admin 'admin' created (pass: admin#123).")

    # -------------------- SEED BOT SETTINGS --------------------
    defaults = [
        {"key": "telegram_bot_token",  "value": "", "updated_at": datetime.now(timezone.utc)},
        {"key": "telegram_all_logs",   "value": "", "updated_at": datetime.now(timezone.utc)},
        {"key": "telegram_boost_logs", "value": "", "updated_at": datetime.now(timezone.utc)},
        {"key": "telegram_auto_logs",  "value": "", "updated_at": datetime.now(timezone.utc)},
        {"key": "discord_bot_token",   "value": "", "updated_at": datetime.now(timezone.utc)},
        {"key": "discord_all_logs",    "value": "", "updated_at": datetime.now(timezone.utc)},
        {"key": "discord_boost_logs",  "value": "", "updated_at": datetime.now(timezone.utc)},
        {"key": "discord_auto_logs",   "value": "", "updated_at": datetime.now(timezone.utc)},
    ]
    for d in defaults:
        bot_settings_col.update_one({"key": d["key"]}, {"$setOnInsert": d}, upsert=True)
    print("[SEED] Bot settings initialized.")

    print("\n[✅] Database setup complete.\n")


if __name__ == "__main__":
    setup_database()