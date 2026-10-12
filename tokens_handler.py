# ================== IMPORTS ==================
import asyncio
import json
import pymongo
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pathlib import Path
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
import os
from config import JWT_SERVERS, MONGO_URI, DB_NAME, REGIONS
import requests as req_lib
# ================== TIMEZONE ==================
try:
    PARIS_TZ = ZoneInfo("Europe/Paris")
except ZoneInfoNotFoundError:
    PARIS_TZ = ZoneInfo("UTC")

# ================== CONSTANTS ==================
BATCH_SIZE = 50
CHECK_INTERVAL = 10
REFRESH_INTERVAL = 6 * 60 * 60
TEMP_EXPIRE_LIMIT = 30 * 60
TARGET_TOKENS = 220        # Minimum target of active tokens
LOW_TOKEN_THRESHOLD = 220 # Threshold triggering differential refresh


# ================== GLOBAL VARIABLES ==================
client = None
db = None
token_state = {}
processing = {}
REGION_FILE_CACHE = {}


import logging

# ================== LOGGING ==================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

_http_client: httpx.AsyncClient | None = None

def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=10.0),
            trust_env=False,
            follow_redirects=True,
        )
    return _http_client

# ================== JWT BACKGROUND ==================
jwt_sending = False


def region_data_exists(region: str) -> bool:
    if region in REGION_FILE_CACHE:
        return REGION_FILE_CACHE[region]
    base = Path(__file__).parent / "data"
    exists = (base / f"{region.lower()}_data.json").exists() or \
             (base / f"{region.lower()}_tokens.json").exists()
    REGION_FILE_CACHE[region] = exists
    return exists

def _get_accounts_file_path(region: str) -> Path:
    base = Path(__file__).parent / "data"
    legacy = base / f"{region.lower()}_data.json"
    return legacy if legacy.exists() else base / f"{region.lower()}_tokens.json"

# ================== MONGO ==================
async def init_mongo():
    global client, db
    try:
        client = AsyncIOMotorClient(MONGO_URI)
        await client.admin.command("ping")
        db_name = DB_NAME if DB_NAME and isinstance(DB_NAME, str) else "like_api"
        db = client[db_name]
        print(f"Connected to MongoDB successfully. DB = {db_name}")
    except Exception as e:
        print(f"[ERROR] MongoDB issue: {e}")
        raise

# ================== TOKEN STATE ==================
async def _load_region_state(region: str, state_collection) -> None:
    file_path = _get_accounts_file_path(region)

    async def read_account_count():
        if not file_path.exists():
            return 0
        try:
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(None, file_path.read_text, "utf-8")
            data = json.loads(raw)
            return len(data) if isinstance(data, list) else 0
        except Exception:
            return 0

    doc, account_count = await asyncio.gather(
        state_collection.find_one({"region": region}),
        read_account_count(),
    )

    if not doc:
        doc = {
            "region": region,
            "success_count": 0,
            "last_token_update_time": None,
            "current_index": 0,
            "refresh_done": False,
            "refresh_count": 0,
            "account_count": account_count,
        }
        await state_collection.insert_one(doc)

    token_state[region] = {
        "success_count": doc.get("success_count", 0),
        "last_token_update_time": doc.get("last_token_update_time"),
        "current_index": doc.get("current_index", 0),
        "refresh_done": doc.get("refresh_done", False),
        "refresh_count": doc.get("refresh_count", 0),
        "account_count": doc.get("account_count", account_count),
    }

async def load_token_state():
    state_collection = db.get_collection("token_state")
    valid_regions = [r for r in REGIONS if region_data_exists(r)]
    skipped = set(REGIONS) - set(valid_regions)
    for r in skipped:
        print(f"[{r}] SKIP - no data file found")
    await asyncio.gather(*[_load_region_state(r, state_collection) for r in valid_regions])

async def save_token_state(region, updates):
    await db.get_collection("token_state").update_one(
        {"region": region}, {"$set": updates}
    )
    if region in token_state:
        token_state[region].update(updates)

# ================== REFRESH TOKENS ==================
async def refresh_tokens(region, should_update_index=True, count: int | None = None):
    file_path = _get_accounts_file_path(region)
    try:
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(None, file_path.read_text, "utf-8")
        data = json.loads(raw)
    except Exception:
        return 0

    if not data or not isinstance(data, list):
        return 0

    # ── UIDs already present in DB (to exclude) ──
    main_col = db.get_collection(f"{region.lower()}_tokens")
    existing_docs = await main_col.find({}, {"uid": 1, "_id": 0}).to_list(None)
    existing_uids = {doc["uid"] for doc in existing_docs}

    r = len(data) if region in ["AG", "NX"] else 220
    start_index = token_state[region].get("current_index", 0)

    # ── Circular traversal from start_index, skip UIDs already in DB ──
    # We collect up to `count` valid accounts (or all if count=None)
    accounts_to_fetch = []
    for i in range(len(data)):  # iterate max len(data) to avoid infinite loop
        acc = data[(start_index + i) % len(data)]
        uid = acc.get("uid")
        password = acc.get("password")
        if not uid or not password:
            continue
        if uid in existing_uids:
            continue  # already in DB → skip, move forward
        accounts_to_fetch.append(acc)
        if count is not None and len(accounts_to_fetch) >= count:
            break
        if count is None and len(accounts_to_fetch) >= r:
            break

    if not accounts_to_fetch:
        print(f"[{region}] All accounts already in DB - skipping")
        return 0
    if len(accounts_to_fetch) >250:
        fetching_count = 250
    else :
        fetching_count = len(accounts_to_fetch)
    print(f"[{region}] {len(existing_uids)} already in DB, fetching {fetching_count} accounts (start_index={start_index})")

    temp_col = db.get_collection(f"{region.lower()}_temp_tokens")
    await temp_col.delete_many({})

    token_docs = []
    http = get_http_client()
    sem = asyncio.Semaphore(50)

    async def fetch_token(uid, password, jwt_server):
        async with sem:
            for attempt in range(2):  # 1 retry
                try:
                    # 🔥 requests use koro, httpx er bodole
                    url = f"{jwt_server}?uid={uid}&password={password}"
                    res = req_lib.get(url, timeout=15, proxies={"http": None, "https": None})
                    res.raise_for_status()
                    res_data = res.json()
                    token = res_data.get("token")
                    account_id = res_data.get("account_id")
                    if token and token != "N/A":
                        token_docs.append({
                            "account_id": account_id or uid,
                            "uid": uid,
                            "token": token,
                            "level": res_data.get("level"),
                            "nickname": res_data.get("nickname"),
                            "timestamp": datetime.now(PARIS_TZ),
                        })
                    return

                except httpx.ConnectTimeout:
                    if attempt == 0:
                        await asyncio.sleep(1)
                        continue
                    logger.warning(f"[{region}] Connection timeout - uid={uid} - {jwt_server}")
                except httpx.ReadTimeout:
                    if attempt == 0:
                        await asyncio.sleep(1)
                        continue
                    logger.warning(f"[{region}] Read timeout - uid={uid} - {jwt_server}")
                except httpx.ConnectError:
                    logger.error(f"[{region}] Server unreachable - {jwt_server}")
                    return
                except httpx.HTTPStatusError as e:
                    logger.error(f"[{region}] HTTP {e.response.status_code} - uid={uid}")
                    return
                except Exception as e:
                    logger.error(f"[{region}] Unexpected error - uid={uid} - {type(e).__name__}: {e}")
                    return

    tasks = [
        fetch_token(
            accounts_to_fetch[i]["uid"],
            accounts_to_fetch[i]["password"],
            JWT_SERVERS[i % len(JWT_SERVERS)],
        )
        for i in range(fetching_count)
    ]

    await asyncio.gather(*tasks)

    if token_docs:
        await temp_col.insert_many(token_docs)
        if should_update_index:
            await save_token_state(region, {
                # Advance the index by the actual number of accounts traversed (including skipped ones)
                "current_index": (start_index + fetching_count) % len(data),
                "last_token_update_time": datetime.now(PARIS_TZ),
                "refresh_count": len(token_docs),
                "account_count": len(data),
            })

    print(f"[{region}] OK - {len(token_docs)} tokens generated")
    return len(token_docs)
# ================== MOVE TOKENS ==================
async def move_tokens(region, merge: bool = False):
    temp_col = db.get_collection(f"{region.lower()}_temp_tokens")
    main_col = db.get_collection(f"{region.lower()}_tokens")

    threshold = datetime.now(PARIS_TZ) - timedelta(seconds=TEMP_EXPIRE_LIMIT)
    tokens = await temp_col.find({"timestamp": {"$gte": threshold}}).to_list(None)

    if not tokens:
        return False

    clean_tokens = [{k: v for k, v in t.items() if k != "_id"} for t in tokens]

    if merge:
        # Differential mode: ADDS new tokens without removing existing ones.
        # Upsert by uid to avoid duplicates.
        ops = [
            pymongo.UpdateOne(
                {"uid": t["uid"]},
                {"$set": t},
                upsert=True,
            )
            for t in clean_tokens
        ]
        if ops:
            await main_col.bulk_write(ops, ordered=False)
        logger.info(f"[{region}] Merge - {len(clean_tokens)} tokens added/updated")
    else:
        # Classic mode: full collection replacement
        await main_col.delete_many({})
        await main_col.insert_many(clean_tokens)

    await temp_col.delete_many({})

    await save_token_state(region, {
        "success_count": 0,
        "refresh_done": False,
        "last_token_update_time": datetime.now(PARIS_TZ),
    })

    print(f"[{region}] OK - tokens moved ({'merge' if merge else 'replace'})")
    return True

# ================== CHECK LOOP ==================
async def check_loop():
    now = datetime.now(PARIS_TZ).timestamp()

    for region in REGIONS:
        if processing.get(region) or not region_data_exists(region):
            continue

        processing[region] = True
        try:
            state = token_state.get(region, {})
            success_count = state.get("success_count", 0)
            last = state.get("last_token_update_time")
            last_ts = last.timestamp() if isinstance(last, datetime) else 0

            main_col = db.get_collection(f"{region.lower()}_tokens")

            # Number of available accounts for this region
            account_count = max(1, state.get("account_count", 0))

            # Dynamic target (never exceeds TARGET_TOKENS)
            target_tokens = min(account_count, TARGET_TOKENS)
            low_threshold = target_tokens

            is_empty = await main_col.find_one({}) is None

            if is_empty:
                print(f"[{region}] WARN - emergency refresh...")
                if await refresh_tokens(region):
                    await move_tokens(region, merge=False)
                continue

            token_count = await main_col.count_documents({})

            # Differential refresh if below threshold
            if token_count < low_threshold:
                needed = target_tokens - token_count

                if needed > 0:
                    print(
                        f"[{region}] Low tokens ({token_count}/{target_tokens}) "
                        f"-> generating {needed} more..."
                    )

                    refreshed = await refresh_tokens(region, count=needed)

                    if refreshed:
                        await move_tokens(region, merge=True)

                continue

            # Periodic refresh
            if now - last_ts >= REFRESH_INTERVAL:
                if await refresh_tokens(region):
                    await move_tokens(region)
                continue

            # Rotation after many uses
            if success_count >= 28:
                moved = await move_tokens(region, merge=True)

                if not moved:
                    if await refresh_tokens(region):
                        await move_tokens(region)
                else:
                    print(f"[{region}] Tokens rotated.")

                continue

        except Exception as e:
            print(f"[{region}] ERROR: {e}")

        finally:
            processing[region] = False
# ================== STARTER ==================
async def start_token_manager():
    await init_mongo()
    await load_token_state()
    print(f"Starting loop every {CHECK_INTERVAL}s...")
    try:
        while True:
            await check_loop()
            await asyncio.sleep(CHECK_INTERVAL)
    finally:
        if client:
            client.close()
        if _http_client and not _http_client.is_closed:
            await _http_client.aclose()

# ================== API ==================
async def get_all_token_states():
    cursor = db.get_collection("token_state").find({})
    return await cursor.to_list(None)