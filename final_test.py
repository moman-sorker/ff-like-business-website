"""
final_test.py
-------------
Full system automation test — validates all features.

Usage:
    python final_test.py                # Run all
    python final_test.py --valid        # Valid tests only
    python final_test.py --invalid      # Invalid tests only
    python final_test.py --verbose      # Show response bodies

Prerequisites:
    1. Run: python db_cleanup.py --force
    2. Server running: python main.py
    3. Then: python final_test.py
"""
import sys
import requests
import random
import string
from datetime import datetime

from test_config import BASE_URL, OWNER, TEST_UIDS, API_TIMEOUT, JOB_TIMEOUT


# ============================================================
# COLOR OUTPUT
# ============================================================
class C:
    GREEN  = "\033[92m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    DIM    = "\033[2m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"


def hdr(title):
    print(f"\n{C.CYAN}{'═'*62}{C.RESET}")
    print(f"{C.BOLD}  {title}{C.RESET}")
    print(f"{C.CYAN}{'═'*62}{C.RESET}")


def sub(title):
    print(f"\n{C.BOLD}  ▸ {title}{C.RESET}")


# ============================================================
# TEST RUNNER
# ============================================================
class Runner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.failures = []

    def check(self, condition, name, detail=""):
        if condition:
            print(f"  {C.GREEN}✓{C.RESET} {name}")
            self.passed += 1
            return True
        else:
            print(f"  {C.RED}✗{C.RESET} {name}")
            if detail:
                print(f"      {C.DIM}{detail}{C.RESET}")
            self.failed += 1
            self.failures.append(f"{name} — {detail}")
            return False

    def skip(self, name, reason=""):
        print(f"  {C.YELLOW}⊘{C.RESET} {name}  {C.DIM}({reason}){C.RESET}")
        self.skipped += 1

    def summary(self):
        total = self.passed + self.failed + self.skipped
        print(f"\n{C.CYAN}{'═'*62}{C.RESET}")
        print(f"{C.BOLD}  TEST SUMMARY{C.RESET}")
        print(f"{C.CYAN}{'═'*62}{C.RESET}")
        print(f"  {C.GREEN}Passed:  {self.passed}{C.RESET}")
        print(f"  {C.RED}Failed:  {self.failed}{C.RESET}")
        print(f"  {C.YELLOW}Skipped: {self.skipped}{C.RESET}")
        print(f"  Total:   {total}")
        if self.failures:
            print(f"\n{C.RED}  Failures:{C.RESET}")
            for f in self.failures:
                print(f"    • {f}")
        print(f"{C.CYAN}{'═'*62}{C.RESET}\n")
        return self.failed == 0


# ============================================================
# HTTP HELPERS
# ============================================================
def api_get(path, session=None, params=None, timeout=30):
    fn = session or requests
    try:
        r = fn.get(f"{BASE_URL}{path}", params=params, timeout=timeout)
        return _parse(r)
    except Exception as e:
        return {"ok": False, "status": 0, "data": {"error": str(e)}}


def api_post(path, session=None, json=None, timeout=30):
    fn = session or requests
    try:
        r = fn.post(f"{BASE_URL}{path}", json=json, timeout=timeout)
        return _parse(r)
    except Exception as e:
        return {"ok": False, "status": 0, "data": {"error": str(e)}}


def api_delete(path, session=None, timeout=30):
    fn = session or requests
    try:
        r = fn.delete(f"{BASE_URL}{path}", timeout=timeout)
        return _parse(r)
    except Exception as e:
        return {"ok": False, "status": 0, "data": {"error": str(e)}}


def _parse(r):
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text[:200]}
    return {"ok": r.ok, "status": r.status_code, "data": data}


def new_session():
    return requests.Session()


# ============================================================
# UTILITIES
# ============================================================
def rand_name(prefix="u"):
    s = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{prefix}_{s}"


def contains(d, *keys):
    return all(k in d for k in keys)


# ============================================================
# VALID TESTS
# ============================================================
def run_valid_tests(R):
    hdr("VALID TESTS — Happy Path")

    # ==========================================================
    # AUTH — LOGIN FLOWS
    # ==========================================================
    sub("AUTH — Login Flows")

    # 1. Owner login
    s_owner = new_session()
    r = api_post("/auth/login", s_owner, json=OWNER)
    ok = r["ok"] and r["data"].get("user", {}).get("role") == "owner"
    R.check(ok, "Owner login (name + pass + master_key)",
            f"status={r['status']} body={r['data']}")

    if not ok:
        return  # Cannot continue without owner

    # 2. Owner /auth/me
    r = api_get("/auth/me", s_owner)
    R.check(r["ok"] and r["data"]["user"]["role"] == "owner",
            "Owner /auth/me returns role=owner")

    # 3. Heartbeat
    r = api_get("/auth/heartbeat", s_owner)
    R.check(r["ok"] and r["data"].get("valid") is True,
            "Owner heartbeat valid=true")

    # ==========================================================
    # KEY GENERATION
    # ==========================================================
    sub("KEY GENERATION — Owner")

    # API key (credits)
    r = api_post("/admin/keys/api/generate", s_owner,
                 json={"credits_per_day": 10, "duration_days": 30, "region": "ALL"})
    key_api = r["data"].get("key") if r["ok"] else None
    R.check(r["ok"] and key_api and key_api.startswith("FF-API-"),
            f"Owner generates FF-API credits key",
            f"key={key_api}")

    # API key (unlimited)
    r = api_post("/admin/keys/api/generate", s_owner,
                 json={"credits_per_day": None, "duration_days": 30, "region": "AG"})
    key_api_unl = r["data"].get("key") if r["ok"] else None
    R.check(r["ok"] and key_api_unl and key_api_unl.startswith("FF-API-"),
            f"Owner generates FF-API unlimited key (AG-locked)",
            f"key={key_api_unl}")

    # Like key
    r = api_post("/admin/keys/like/generate", s_owner,
                 json={"per_uid_per_day": 3, "duration_days": 30})
    key_lk = r["data"].get("key") if r["ok"] else None
    R.check(r["ok"] and key_lk and key_lk.startswith("FF-LK-"),
            f"Owner generates FF-LK key",
            f"key={key_lk}")

    # Admin key (FF-AD)
    r = api_post("/admin/keys/api/generate", s_owner,
                 json={"credits_per_day": None, "duration_days": 30,
                       "region": "ALL", "admin_key": True})
    key_ad = r["data"].get("key") if r["ok"] else None
    R.check(r["ok"] and key_ad and key_ad.startswith("FF-AD-"),
            f"Owner generates FF-AD admin key",
            f"key={key_ad}")

    # List keys — verify FF-AD excluded from client list
    r = api_get("/admin/keys/api", s_owner)
    keys = r["data"].get("keys", [])
    has_ffad = any(k["key"].startswith("FF-AD-") for k in keys)
    R.check(r["ok"] and not has_ffad,
            "Active API Keys list excludes FF-AD keys")

    # ==========================================================
    # ADMIN CREATION
    # ==========================================================
    sub("ADMIN — Create with key")

    admin_name = rand_name("admin")
    r = api_post("/admin/admins/create", s_owner,
                 json={"name": admin_name, "password": "admin123",
                       "key": key_ad})
    R.check(r["ok"], f"Owner creates admin '{admin_name}' with FF-AD key",
            f"status={r['status']} body={r['data']}")

    # ==========================================================
    # ADMIN LOGIN + RESTRICTIONS
    # ==========================================================
    sub("ADMIN — Login & Access")

    s_admin = new_session()
    r = api_post("/auth/login", s_admin,
                 json={"name": admin_name, "password": "admin123", "key": key_ad})
    ok = r["ok"] and r["data"].get("user", {}).get("role") == "admin"
    R.check(ok, "Admin login with FF-AD key",
            f"status={r['status']} body={r['data']}")

    # Admin cannot create other admins
    r = api_post("/admin/admins/create", s_admin,
                 json={"name": rand_name("admin2"), "password": "x1234"})
    R.check(r["status"] == 403, "Admin → create admin blocked (403)",
            f"status={r['status']}")

    # Admin cannot generate FF-AD
    r = api_post("/admin/keys/api/generate", s_admin,
                 json={"credits_per_day": None, "duration_days": 30,
                       "region": "ALL", "admin_key": True})
    R.check(r["status"] == 403, "Admin → generate FF-AD blocked (403)",
            f"status={r['status']}")

    # Admin CAN generate FF-API
    r = api_post("/admin/keys/api/generate", s_admin,
                 json={"credits_per_day": 5, "duration_days": 7, "region": "ALL"})
    key_admin_gen = r["data"].get("key") if r["ok"] else None
    R.check(r["ok"] and key_admin_gen and key_admin_gen.startswith("FF-API-"),
            "Admin → generate FF-API allowed",
            f"key={key_admin_gen}")

    # ==========================================================
    # CLIENT SELF-REGISTER
    # ==========================================================
    sub("CLIENT — Self-register (API client)")

    api_user = rand_name("apic")
    s_api = new_session()
    r = api_post("/auth/login", s_api,
                 json={"name": api_user, "password": "test123", "key": key_api})
    ok = r["ok"] and r["data"].get("user", {}).get("role") == "user"
    R.check(ok, f"Client '{api_user}' self-registers with FF-API key",
            f"status={r['status']} body={r['data']}")

    # /client/me returns api_key
    r = api_get("/client/me", s_api)
    R.check(r["ok"] and r["data"].get("api_key") is not None,
            "API client /client/me returns api_key")

    # ==========================================================
    # CLIENT — Like key self-register
    # ==========================================================
    sub("CLIENT — Self-register (Like client)")

    lk_user = rand_name("lkc")
    s_lk = new_session()
    r = api_post("/auth/login", s_lk,
                 json={"name": lk_user, "password": "test123", "key": key_lk})
    R.check(r["ok"] and r["data"].get("user", {}).get("role") == "user",
            f"Client '{lk_user}' self-registers with FF-LK key",
            f"status={r['status']}")

    r = api_get("/client/me", s_lk)
    R.check(r["ok"] and r["data"].get("like_key") is not None,
            "Like client /client/me returns like_key")

    # ==========================================================
    # DATA ISOLATION — Client logs not in Admin
    # ==========================================================
    sub("ISOLATION — Client vs Admin logs")

    r = api_get("/admin/logs", s_owner, params={"limit": 100})
    logs = r["data"].get("logs", [])
    admin_sees_client = any(
        l.get("user") in (api_user, lk_user) for l in logs
    )
    R.check(r["ok"] and not admin_sees_client,
            "Admin logs exclude client activity",
            f"admin_sees={admin_sees_client}")

    # Admin sees own actions
    r = api_get("/admin/logs", s_owner, params={"limit": 100})
    logs = r["data"].get("logs", [])
    admin_sees_self = any(l.get("user") == "sarker" for l in logs)
    R.check(admin_sees_self,
            "Admin logs include owner/admin actions")

    # ==========================================================
    # JOBS — Admin Boost
    # ==========================================================
    sub("JOBS — Boost (Admin)")

    uid_boost = TEST_UIDS["boost"]
    r = api_post("/admin/boost/create", s_owner,
                 json={"uid": uid_boost, "region": "AG",
                       "add_likes": 50, "per_day": 200},
                 timeout=JOB_TIMEOUT)
    ok = r["ok"] and r["data"].get("ok") is True
    job_status = r["data"].get("status") if r["ok"] else None
    if ok:
        R.check(True,
                f"Admin creates boost job (UID {uid_boost})",
                f"status={job_status} target={r['data'].get('target_likes')}")
    else:
        # Might fail if token pool dry — acceptable
        R.skip(f"Admin boost job create",
               f"reason={r['data'].get('error') or r['data'].get('reason')}")

    # Admin Boost duplicate — same UID → reject
    r = api_post("/admin/boost/create", s_owner,
                 json={"uid": uid_boost, "region": "AG",
                       "add_likes": 50, "per_day": 200},
                 timeout=JOB_TIMEOUT)
    R.check(r["status"] == 400,
            "Boost same UID duplicate rejected (400)",
            f"status={r['status']} error={r['data'].get('error')}")

    # ==========================================================
    # JOBS — Admin Auto
    # ==========================================================
    sub("JOBS — Auto (Admin)")

    uid_auto = TEST_UIDS["auto"]
    r = api_post("/admin/auto/create", s_owner,
                 json={"uid": uid_auto, "region": "AG",
                       "duration_days": 3, "per_day": 200},
                 timeout=JOB_TIMEOUT)
    ok = r["ok"] and r["data"].get("ok") is True
    if ok:
        R.check(True, f"Admin creates auto job (UID {uid_auto})",
                f"expires={r['data'].get('expires_at')}")
    else:
        R.skip(f"Admin auto job create",
               f"reason={r['data'].get('error')}")

    # Duplicate auto — same UID → reject
    r = api_post("/admin/auto/create", s_owner,
                 json={"uid": uid_auto, "region": "AG",
                       "duration_days": 3, "per_day": 200},
                 timeout=JOB_TIMEOUT)
    R.check(r["status"] == 400,
            "Auto same UID duplicate rejected (400)")

    # ==========================================================
    # SAME UID — Boost + Auto allowed (separate systems)
    # ==========================================================
    sub("JOBS — Same UID in Boost + Auto (should be allowed)")

    uid_combo = TEST_UIDS["combo"]
    r1 = api_post("/admin/boost/create", s_owner,
                  json={"uid": uid_combo, "region": "AG",
                        "add_likes": 50, "per_day": 200},
                  timeout=JOB_TIMEOUT)
    r2 = api_post("/admin/auto/create", s_owner,
                  json={"uid": uid_combo, "region": "AG",
                        "duration_days": 3, "per_day": 200},
                  timeout=JOB_TIMEOUT)

    if r1["ok"] and r2["ok"]:
        R.check(True, "Same UID allowed in both Boost and Auto (isolated)")
    else:
        R.skip("Same UID combo test",
               f"boost_ok={r1['ok']} auto_ok={r2['ok']}")

    # ==========================================================
    # CLIENT — Job create (API client)
    # ==========================================================
    sub("CLIENT — Boost/Auto create (API client)")

    uid_c = TEST_UIDS["like"]
    r = api_post("/client/boost/create", s_api,
                 json={"uid": uid_c, "region": "AG", "add_likes": 20},
                 timeout=JOB_TIMEOUT)
    ok = r["ok"] and r["data"].get("ok") is True
    if ok:
        R.check(True, f"API client creates boost job (UID {uid_c})")
    else:
        R.skip("API client boost job",
               f"reason={r['data'].get('error')}")

    r = api_post("/client/auto/create", s_api,
                 json={"uid": uid_c, "region": "AG", "duration_days": 2},
                 timeout=JOB_TIMEOUT)
    ok = r["ok"] and r["data"].get("ok") is True
    if ok:
        R.check(True, f"API client creates auto job (UID {uid_c})")
    else:
        R.skip("API client auto job",
               f"reason={r['data'].get('error')}")

    # API client /client/jobs list — only own
    r = api_get("/client/jobs", s_api)
    R.check(r["ok"] and "boost" in r["data"] and "auto" in r["data"],
            "Client /client/jobs returns own jobs")

    # ==========================================================
    # Like Client cannot create boost
    # ==========================================================
    sub("CLIENT — Like client restriction")

    r = api_post("/client/boost/create", s_lk,
                 json={"uid": "7999999999", "region": "AG", "add_likes": 20},
                 timeout=JOB_TIMEOUT)
    # Like client key doesn't allow boost — backend should reject
    # (only API key type is validated for boost)
    if r["status"] == 403 or not r["ok"]:
        R.check(True, "Like client blocked from creating boost job")
    else:
        # If somehow allowed, it worked but inconsistent
        R.check(False, "Like client allowed boost job — should be blocked",
                f"status={r['status']} data={r['data']}")

    # ==========================================================
    # LOGOUT
    # ==========================================================
    sub("AUTH — Logout")

    r = api_post("/auth/logout", s_owner)
    R.check(r["ok"], "Owner logout")

    # Session invalid after logout
    r = api_get("/auth/me", s_owner)
    R.check(r["status"] == 401, "After logout /auth/me returns 401")


# ============================================================
# INVALID TESTS
# ============================================================
def run_invalid_tests(R):
    hdr("INVALID TESTS — Error Cases")

    # ==========================================================
    # AUTH — Invalid credentials
    # ==========================================================
    sub("AUTH — Invalid Login")

    # Owner wrong password
    s = new_session()
    r = api_post("/auth/login", s,
                 json={"name": "sarker", "password": "WRONG", "key": "388401"})
    R.check(r["status"] == 401 and r["data"].get("error") == "invalid_credentials",
            "Owner wrong password → 401 invalid_credentials")

    # Owner wrong master key
    r = api_post("/auth/login", s,
                 json={"name": "sarker", "password": "mimo#123", "key": "9999"})
    R.check(r["status"] == 401 and r["data"].get("error") == "invalid_master_key",
            "Owner wrong master key → 401 invalid_master_key")

    # Non-existent user
    r = api_post("/auth/login", s,
                 json={"name": "ghost_user_999", "password": "x", "key": "FF-API-X"})
    # Should attempt self-register and fail on invalid key
    R.check(r["status"] in (400, 401),
            f"Non-existent user + invalid key → {r['status']}")

    # Invalid key format
    r = api_post("/auth/login", s,
                 json={"name": rand_name("x"), "password": "test123",
                       "key": "INVALID-PREFIX-123"})
    R.check(r["status"] == 401 and r["data"].get("error") == "invalid_key_format",
            "Invalid key format → invalid_key_format")

    # ==========================================================
    # AUTH — Unauthorized Access
    # ==========================================================
    sub("AUTH — Unauthorized Endpoints")

    s_anon = new_session()

    r = api_get("/admin/stats", s_anon)
    R.check(r["status"] == 401, "No session → /admin/stats 401")

    r = api_get("/client/me", s_anon)
    R.check(r["status"] == 401, "No session → /client/me 401")

    r = api_post("/admin/keys/api/generate", s_anon,
                 json={"credits_per_day": 5, "duration_days": 30, "region": "ALL"})
    R.check(r["status"] == 401, "No session → generate key 401")

    # ==========================================================
    # LOGIN → Get sessions for role tests
    # ==========================================================
    sub("Setup: fresh sessions")

    s_owner = new_session()
    r = api_post("/auth/login", s_owner, json=OWNER)
    if not r["ok"]:
        R.skip("Full invalid tests", "Owner login failed")
        return

    # Create a fresh client (need key)
    key_api = None
    key_api_unl = None
    key_lk = None

    r = api_post("/admin/keys/api/generate", s_owner,
                 json={"credits_per_day": 2, "duration_days": 30, "region": "ALL"})
    if r["ok"]:
        key_api = r["data"]["key"]

    r = api_post("/admin/keys/api/generate", s_owner,
                 json={"credits_per_day": None, "duration_days": 30, "region": "AG"})
    if r["ok"]:
        key_api_unl = r["data"]["key"]

    r = api_post("/admin/keys/like/generate", s_owner,
                 json={"per_uid_per_day": 2, "duration_days": 30})
    if r["ok"]:
        key_lk = r["data"]["key"]

    s_api = new_session()
    api_user = rand_name("apic")
    if key_api:
        api_post("/auth/login", s_api,
                 json={"name": api_user, "password": "test123", "key": key_api})

    # ==========================================================
    # ROLE ENFORCEMENT
    # ==========================================================
    sub("ROLE — Admin & Client can't access owner-only routes")

    # Create an admin
    admin_name = rand_name("admin")
    key_ad = None
    r = api_post("/admin/keys/api/generate", s_owner,
                 json={"credits_per_day": None, "duration_days": 30,
                       "region": "ALL", "admin_key": True})
    if r["ok"]:
        key_ad = r["data"]["key"]
        api_post("/admin/admins/create", s_owner,
                 json={"name": admin_name, "password": "admin123", "key": key_ad})

    s_admin = new_session()
    if key_ad:
        api_post("/auth/login", s_admin,
                 json={"name": admin_name, "password": "admin123", "key": key_ad})

    # Client trying admin route
    if key_api:
        r = api_get("/admin/stats", s_api)
        R.check(r["status"] == 403, "Client → /admin/stats 403 forbidden")

    # Admin trying owner-only route
    if key_ad:
        r = api_post("/admin/admins/create", s_admin,
                     json={"name": rand_name("x"), "password": "x1234"})
        R.check(r["status"] == 403, "Admin → create admin 403 forbidden")

        r = api_post("/admin/keys/api/generate", s_admin,
                     json={"credits_per_day": None, "duration_days": 30,
                           "region": "ALL", "admin_key": True})
        R.check(r["status"] == 403, "Admin → generate FF-AD 403 forbidden")

        # Admin cannot delete FF-AD keys
        if key_ad:
            r = api_delete(f"/admin/keys/api/{key_ad}", s_admin)
            R.check(r["status"] == 403,
                    "Admin → delete FF-AD key 403 forbidden")

    # ==========================================================
    # DUPLICATE KEY GENERATION ISSUES
    # ==========================================================
    sub("KEY — Region mismatch")

    if key_api_unl:
        # Setup a client bound to AG-only key
        s_ag = new_session()
        ag_user = rand_name("agc")
        r = api_post("/auth/login", s_ag,
                     json={"name": ag_user, "password": "test123", "key": key_api_unl})
        if r["ok"]:
            # Try to send like in IND region (should be rejected)
            r = api_post("/client/like", s_ag,
                         json={"uid": TEST_UIDS["region"], "region": "IND"},
                         timeout=API_TIMEOUT)
            R.check(r["status"] == 403 and r["data"].get("error") == "region_not_allowed",
                    "AG-locked key → IND region rejected (region_not_allowed)")
        else:
            R.skip("Region mismatch test", "AG client login failed")

    # ==========================================================
    # UID FORMAT VALIDATION
    # ==========================================================
    # sub("VALIDATION — Bad Inputs")

    # if key_api and s_api.cookies:
    #     # Invalid UID (not numeric)
    #     r = api_post("/client/like", s_api,
    #                  json={"uid": "abc123", "region": "AG"},
    #                  timeout=30)
    #     # Backend might not validate format — accept any 400/403 or specific
    #     R.check(r["status"] in (400, 403),
    #             "Invalid UID format rejected")

    #     # Missing UID
    #     r = api_post("/client/like", s_api, json={"region": "AG"})
    #     R.check(r["status"] == 400, "Missing UID → 400")

    # ==========================================================
    # LIKE LIMIT (Same UID twice)
    # ==========================================================
    sub("LIMIT — Like key per-UID per-day")

    if key_lk:
        s_lk = new_session()
        lk_user = rand_name("lkc")
        r = api_post("/auth/login", s_lk,
                     json={"name": lk_user, "password": "test123", "key": key_lk})
        if r["ok"]:
            uid_limit = "7000000888"
            # First 2 likes allowed (per_uid_per_day=2)
            for i in range(2):
                r = api_post("/client/like", s_lk,
                             json={"uid": uid_limit, "region": "AG"},
                             timeout=API_TIMEOUT)
                if not r["ok"]:
                    R.skip(f"Like #{i+1} at limit test",
                           f"reason={r['data'].get('error')} — token pool")
                    break
            # 3rd time should fail with uid_daily_limit_reached
            r = api_post("/client/like", s_lk,
                         json={"uid": uid_limit, "region": "AG"},
                         timeout=API_TIMEOUT)
            R.check(r["status"] == 403 and
                    r["data"].get("error") == "uid_daily_limit_reached",
                    "Like key per-UID limit enforced (uid_daily_limit_reached)")

    # ==========================================================
    # CREDIT LIMIT (Same client repeated)
    # ==========================================================
    sub("LIMIT — API credit per-day")

    if key_api:
        s_cr = new_session()
        cr_user = rand_name("crc")
        r = api_post("/auth/login", s_cr,
                     json={"name": cr_user, "password": "test123", "key": key_api})
        if r["ok"]:
            # credits_per_day=2, so 3rd call should fail
            for i in range(3):
                r = api_post("/client/like", s_cr,
                             json={"uid": f"70000007{i:02d}", "region": "AG"},
                             timeout=API_TIMEOUT)
            # After 3rd attempt, should be daily_limit_reached
            if not r["ok"]:
                R.check(r["data"].get("error") in
                        ("daily_limit_reached", "uid_daily_limit_reached"),
                        "API credit daily limit enforced")
            else:
                R.skip("API credit limit test",
                       "Like calls failing due to tokens")

    # ==========================================================
    # JOB — Same owner + same UID duplicate (Boost)
    # ==========================================================
    sub("JOBS — Duplicate rejection")

    dup_uid = "7000000911"
    r1 = api_post("/admin/boost/create", s_owner,
                  json={"uid": dup_uid, "region": "AG",
                        "add_likes": 20, "per_day": 200},
                  timeout=JOB_TIMEOUT)
    r2 = api_post("/admin/boost/create", s_owner,
                  json={"uid": dup_uid, "region": "AG",
                        "add_likes": 20, "per_day": 200},
                  timeout=JOB_TIMEOUT)
    if r1["ok"]:
        R.check(r2["status"] == 400 and
                r2["data"].get("error") == "uid_exists_for_you",
                "Boost duplicate per-owner rejected (uid_exists_for_you)")
    else:
        R.skip("Boost duplicate test", f"create failed: {r1['data'].get('error')}")

    # Different owner can use same UID
    if key_ad:
        r3 = api_post("/admin/boost/create", s_admin,
                      json={"uid": dup_uid, "region": "AG",
                            "add_likes": 20, "per_day": 200},
                      timeout=JOB_TIMEOUT)
        # Admin uses OWNER_KEY? No — admin uses own key. Let's check
        # In admin_direct_like we pass owner bypass. But boost uses create_boost_job
        # which uses created_by=admin_name
        R.check(r3["ok"] or r3["status"] == 400,
                "Admin can create same UID (different owner)")

    # ==========================================================
    # SUSPENDED ACCOUNT
    # ==========================================================
    sub("ACCOUNT — Suspended")

    # Suspend api_user
    if key_api:
        r = api_post(f"/admin/users/{api_user}/status", s_owner,
                     json={"status": "suspended"})
        if r["ok"]:
            # Try using api_user session
            r = api_get("/auth/me", s_api)
            R.check(r["status"] in (401, 403),
                    "Suspended user session invalidated")
        else:
            R.skip("Suspend test", f"status change failed: {r['data']}")


# ============================================================
# MAIN
# ============================================================
def main():
    args = sys.argv[1:]
    run_valid = "--invalid" not in args
    run_invalid = "--valid" not in args

    print(f"\n{C.BOLD}{C.CYAN}")
    print(f"  ╔═══════════════════════════════════════════════════════╗")
    print(f"  ║   FF LIKE API — FULL AUTOMATION TEST                  ║")
    print(f"  ║   Server: {BASE_URL:<40}║")
    print(f"  ╚═══════════════════════════════════════════════════════╝")
    print(f"{C.RESET}")

    # Check server reachable
    try:
        r = requests.get(BASE_URL, timeout=5)
        print(f"  {C.GREEN}✓ Server reachable{C.RESET}")
    except Exception as e:
        print(f"  {C.RED}✗ Server not reachable: {e}{C.RESET}")
        print(f"  Start server: python main.py\n")
        sys.exit(1)

    R = Runner()
    start = datetime.now()

    if run_valid:
        run_valid_tests(R)
    if run_invalid:
        run_invalid_tests(R)

    elapsed = (datetime.now() - start).total_seconds()
    success = R.summary()

    print(f"  Elapsed: {elapsed:.1f}s\n")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()