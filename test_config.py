"""
test_config.py
--------------
Shared config for test automation.
Uses REAL game UIDs collected from production logs.
"""

BASE_URL = "http://127.0.0.1:5000"

# Owner credentials (from config.py defaults)
OWNER = {
    "name":     "sarker",
    "password": "mimo#123",
    "key":      "388401",
}

REGIONS = ["AG", "IND", "NX"]

# 🔥 REAL game UIDs (from production logs / screenshots)
# Each one used only once per test-run cycle.
TEST_UIDS = {
    "boost":    "387531739",      # Original test UID
    "auto":     "1165226079",     # Original test UID
    "like":     "1763683144",     # Romjan1202V
    "combo":    "2432056293",     # Combo (boost + auto same UID)
    "limit":    "5632995543",     # For Like key per-day limit test
    "region":   "2331117045",     # For region-mismatch test
}

# Timeouts
API_TIMEOUT = 90      # like send takes long (tokens)
JOB_TIMEOUT = 60      # job create uses quick fetch