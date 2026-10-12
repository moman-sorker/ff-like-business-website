import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# SERVER
# ============================================================
PORT = int(os.getenv("PORT", 5000))
VERSION = "OB55"

# ============================================================
# JWT TOKEN SERVERS
# ============================================================
JWT_SERVERS = [
    "https://ff-jwt.app/token",
    "https://ff-jwt.app/token",
    "https://ff-jwt.app/token",
    "https://ff-jwt.app/token"
]

# ============================================================
# MONGO
# ============================================================
MONGO_URI = os.getenv("MONGO_URI", "")
DB_NAME = os.getenv("DB_NAME", "sarker_xpert")

# ============================================================
# REGIONS
# ============================================================
REGIONS = ["NX", "AG", "IND"]
SCOPE = "LIKE_CLIENT"

REGION_CONFIG = {
    "IND": {"tokens": "ind_tokens", "url": "https://client.ind.freefiremobile.com", "state": "IND"},
    "NX":  {"tokens": "nx_tokens",  "url": "https://client.us.freefiremobile.com",  "state": "NX"},
    "AG":  {"tokens": "ag_tokens",  "url": "https://clientbp.ppmainecoonghj.com",  "state": "AG"}
}

# ============================================================
# OWNER
# ============================================================
OWNER_NAME = os.getenv("OWNER_NAME", "sarker")
OWNER_PASSWORD = os.getenv("OWNER_PASSWORD", "mimo#123")
OWNER_MASTER_KEY = os.getenv("OWNER_MASTER_KEY", "388401")
OWNER_KEY = os.getenv("OWNER_KEY", "mm")      # 🔥 NEW — URL bypass key

# ============================================================
# BOTS — Tokens only (channel/group IDs are set from bot commands)
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8834273520:AAGYpGRbp88--")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "MTU1ODA2NTIyMjgzOTk2MzcxOA..")

TELEGRAM_OWNER_IDS = os.getenv("TELEGRAM_OWNER_IDS", "6683255978, 7301618403")
DISCORD_OWNER_IDS = os.getenv("DISCORD_OWNER_IDS", "813690215860273202, 1391411334754603058")

# ============================================================
# KEY PREFIXES
# ============================================================
API_KEY_PREFIX = "FF-API"
LIKE_KEY_PREFIX = "FF-LK"
ADMIN_KEY_PREFIX = "FF-AD"    # 🔥 NEW

# ============================================================
# REGION CHOICES (for API key restriction)
# ============================================================
REGION_CHOICES = ["ALL", "AG", "IND", "NX"]

# ============================================================
# SUBSCRIPTION DEFAULTS — NO DEFAULTS (admin must set)
# ============================================================
DEFAULT_CREDITS_PER_DAY = None
DEFAULT_DURATION_DAYS = None
DEFAULT_PER_UID_PER_DAY = None

# ============================================================
# SCHEDULER
# ============================================================
SCHEDULER_HOUR_UTC = 0
CREDITS_RESET_HOUR_UTC = 0
EXPIRE_CHECK_INTERVAL = 300

# ============================================================
# FLASK SESSION
# ============================================================
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE-THIS-IN-PROD")
SESSION_TIMEOUT_MINUTES = 60 * 24