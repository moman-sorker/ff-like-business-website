"""
db_cleanup.py
-------------
Reset DB for fresh testing:
- Removes all client accounts, keys, jobs, logs
- Keeps: owner account, bot settings
- Verifies all critical indexes exist

Usage:
    python db_cleanup.py           # Interactive prompt
    python db_cleanup.py --force   # No prompt
"""
import sys
from pymongo import MongoClient, ASCENDING, DESCENDING
from config import MONGO_URI, DB_NAME, OWNER_NAME


def verify_indexes(db):
    """Ensure compound indexes exist."""
    print("\n[INDEXES] Verifying...")

    required = [
        ("accounts",       [("name", ASCENDING)], True, "name_1"),
        ("api_keys",       [("key", ASCENDING)],  True, "key_1"),
        ("like_keys",      [("key", ASCENDING)],  True, "key_1"),
        ("boost_like",     [("uid", ASCENDING), ("created_by", ASCENDING)], True, "uid_owner_unique"),
        ("auto_like",      [("uid", ASCENDING), ("created_by", ASCENDING)], True, "uid_owner_unique"),
    ]

    for coll_name, keys, unique, expected_name in required:
        coll = db[coll_name]
        existing = [idx["name"] for idx in coll.list_indexes()]
        if expected_name in existing:
            print(f"  ✅ {coll_name}.{expected_name}")
        else:
            try:
                coll.create_index(keys, unique=unique, name=expected_name)
                print(f"  🔨 {coll_name}.{expected_name} (created)")
            except Exception as e:
                print(f"  ⚠️  {coll_name}.{expected_name}: {e}")


def cleanup(force=False):
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    print(f"\n{'='*60}")
    print(f"  DB CLEANUP — {DB_NAME}")
    print(f"{'='*60}")

    # Count before
    counts = {
        "accounts":       db.accounts.count_documents({}),
        "api_keys":       db.api_keys.count_documents({}),
        "like_keys":      db.like_keys.count_documents({}),
        "like_usage":     db.like_usage.count_documents({}),
        "boost_like":     db.boost_like.count_documents({}),
        "auto_like":      db.auto_like.count_documents({}),
        "activity_logs":  db.activity_logs.count_documents({}),
    }

    print("\n[BEFORE]")
    for k, v in counts.items():
        print(f"  • {k:20s} {v:>6}")

    if not force:
        ans = input("\n⚠️  Delete all client data? (y/N): ").strip().lower()
        if ans != "y":
            print("Cancelled.")
            return

    # Delete non-owner accounts
    r_accounts = db.accounts.delete_many({"role": {"$nin": ["owner"]}})
    r_api      = db.api_keys.delete_many({})
    r_like     = db.like_keys.delete_many({})
    r_usage    = db.like_usage.delete_many({})
    r_boost    = db.boost_like.delete_many({})
    r_auto     = db.auto_like.delete_many({})
    r_logs     = db.activity_logs.delete_many({})

    # Reset owner assignments
    db.accounts.update_one(
        {"name": OWNER_NAME},
        {"$unset": {"assigned_api_key": "", "assigned_like_key": "",
                    "session_token": "", "session_expires": ""}},
    )

    print("\n[DELETED]")
    print(f"  • Non-owner accounts:  {r_accounts.deleted_count}")
    print(f"  • API keys:            {r_api.deleted_count}")
    print(f"  • Like keys:           {r_like.deleted_count}")
    print(f"  • Like usage:          {r_usage.deleted_count}")
    print(f"  • Boost jobs:          {r_boost.deleted_count}")
    print(f"  • Auto jobs:           {r_auto.deleted_count}")
    print(f"  • Activity logs:       {r_logs.deleted_count}")

    verify_indexes(db)

    print(f"\n✅ Cleanup complete.\n")
    client.close()


if __name__ == "__main__":
    force = "--force" in sys.argv
    cleanup(force=force)