<div align="center">

# 🔥 FF LIKE API

**Production-Grade Free Fire Like Automation System**

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.x-000000?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com)
[![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248?style=for-the-badge&logo=mongodb&logoColor=white)](https://mongodb.com)
[![OB55](https://img.shields.io/badge/Game_Version-OB55-22d3ee?style=for-the-badge)]()
[![Test](https://img.shields.io/badge/Tests-46%2F46_Pass-22c55e?style=for-the-badge)]()

AES-encrypted protobuf-based API for sending likes to Free Fire players via valid game access tokens. Multi-role auth, subscription system, job scheduler, and real-time Telegram/Discord log broadcasting.

</div>

---

## 📑 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Installation](#-installation)
- [🔐 Credentials Update Guide](#-credentials-update-guide)
- [Database Schema](#-database-schema)
- [API Endpoints](#-api-endpoints)
- [User Roles & Permissions](#-user-roles--permissions)
- [Key Types](#-key-types)
- [Automation Test](#-automation-test)
- [Deployment](#-deployment)
- [Monitoring](#-monitoring)
- [Troubleshooting](#-troubleshooting)

---

## ✨ Features

<table>
<tr>
<td valign="top" width="50%">

### 🎯 Core
- ✅ AES-128-CBC encrypted protobuf requests
- ✅ Multi-region support (AG, IND, NX)
- ✅ Token pool management with auto-refresh
- ✅ 100 concurrent like requests per call
- ✅ Real-time like count fetch (before/after)
- ✅ OB55 game version compatible

### 🔐 Auth & Roles
- ✅ 3-role system (Owner / Admin / User)
- ✅ Session-based authentication
- ✅ Self-register for clients
- ✅ Heartbeat session validation (3s)
- ✅ Auto-logout on suspend/expire

</td>
<td valign="top" width="50%">

### 💼 Jobs
- ✅ Boost Like — milestone-based
- ✅ Auto Like — duration-based
- ✅ Daily scheduler (00:00 UTC)
- ✅ Per-owner job isolation
- ✅ Auto-terminate on key expiry

### 🔑 Subscription System
- ✅ API Keys (`FF-API-*`) — credits/unlimited
- ✅ Like Keys (`FF-LK-*`) — per-UID limit
- ✅ Admin Keys (`FF-AD-*`) — owner-only
- ✅ Region locking
- ✅ Duration-based expiry

### 🤖 Bots & UI
- ✅ Telegram log broadcasting
- ✅ Discord log broadcasting
- ✅ 3 web panels (Login / Admin / Client)
- ✅ 10 animated themes
- ✅ Real-time sync engine

</td>
</tr>
</table>

---

## 🏗 Architecture
┌──────────────────────────┐
│ Free Fire Game API │
│ (GetPlayerPersonalShow) │
│ (LikeProfile) │
└──────────┬───────────────┘
│ AES + Protobuf
│
┌──────────────────────────────────────▼───────────────────────────────────┐
│ FF LIKE API (Flask) │
│ │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │
│ │ Auth Layer │ │ Rate Limit │ │ Scheduler │ │ Token Mgr │ │
│ │ (sessions) │ │ (credits) │ │ (APScheduler)│ │ (refresh) │ │
│ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ │
│ │ │ │ │ │
│ ┌──────▼─────────────────▼─────────────────▼─────────────────▼───────┐ │
│ │ MongoDB (Persistent Layer) │ │
│ │ accounts · api_keys · like_keys · boost_like · auto_like · logs │ │
│ └────────────────────────────────┬───────────────────────────────────┘ │
│ │ │
│ ┌────────────────────────────────▼───────────────────────────────────┐ │
│ │ Frontend (3 Panels) │ │
│ │ ┌────────────┐ ┌────────────┐ ┌────────────┐ │ │
│ │ │ Login Page │ │Admin Panel │ │Client Panel│ │ │
│ │ └────────────┘ └────────────┘ └────────────┘ │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│ │
│ ┌────────────────────────────┐ ┌────────────────────────────┐ │
│ │ Telegram Bot (logs) │ │ Discord Bot (logs) │ │
│ └────────────────────────────┘ └────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘

text

---

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.8+, Flask 2.x |
| **Database** | MongoDB Atlas (motor + pymongo) |
| **Crypto** | pycryptodome (AES-128-CBC) |
| **Protobuf** | google.protobuf 6.30+ |
| **HTTP Client** | aiohttp, httpx, requests |
| **Scheduler** | APScheduler (BackgroundScheduler) |
| **Bots** | python-telegram-bot, discord.py |
| **Frontend** | Vanilla JS + Canvas API |
| **Deployment** | Vercel / Docker / Gunicorn |

---

## 📁 Project Structure
project-api-ob55/
│
├── 📂 app/ # Application modules
│ ├── encryption.py # AES-128-CBC encrypt
│ ├── protobuf_handler.py # Protobuf build/decode
│ └── request_handler.py # HTTP request helpers
│
├── 📂 proto/ # Protobuf definitions
│ ├── init.py
│ ├── like_pb2.py # Like request schema
│ ├── uid_generator_pb2.py # UID request schema
│ └── visit_count_pb2.py # Response parser
│
├── 📂 templates/ # Frontend
│ ├── index.html # Login page
│ ├── admin.html # Admin panel
│ ├── clients.html # Client panel
│ └── 📂 static/
│ ├── 📂 css/
│ │ ├── index.css
│ │ ├── admin.css
│ │ └── clients.css
│ └── 📂 js/
│ ├── index.js
│ ├── admin.js
│ ├── clients.js
│ ├── themes.js # 10 themes
│ └── realtime.js # Real-time sync
│
├── 📄 main.py # Flask app entry
├── 📄 config.py # ⚙️ Configuration
├── 📄 db.py # MongoDB connection
├── 📄 auth.py # Session auth
├── 📄 subscription.py # Like key + sender
├── 📄 subscriptionAPI.py # API key + Boost + Auto
├── 📄 logs.py # Activity + Bot logs
├── 📄 tokens_handler.py # Token pool manager
├── 📄 db_cleanup.py # Test DB reset
├── 📄 test_config.py # Test config
├── 📄 final_test.py # Automation test suite
│
├── 📄 requirements.txt
├── 📄 .env # ⚙️ ENV secrets
├── 📄 vercel.json
├── 📄 README.md
└── 📄 Dockerfile (optional)

text

---

## 🚀 Installation

### Prerequisites

- Python **3.8+**
- MongoDB (local or Atlas)
- Git

### Step 1 — Clone & Setup

```bash
git clone <your-repo-url>
cd project-api-ob55
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
Step 2 — Install Dependencies
bash
pip install -r requirements.txt
Step 3 — Configure .env
⚠️ See Credentials Update Guide below — MUST read

Step 4 — Initialize Database
bash
python db.py
Expected output:

text
[DB] Connected: sarker_xpert
[DB] Indexes created.
[SEED] Owner 'sarker' created.
[SEED] Default admin 'admin' created (pass: admin#123).
[SEED] Bot settings initialized.

[✅] Database setup complete.
Step 5 — Start Server
bash
python main.py
Expected startup log:

text
[SCHEDULER] Started — daily at 00:00 UTC, cleanup every 5 min, init pending every 15 min.
[TG] Poller started.
[DC] Logged in as YourBot#1234
[BOTS] Ready.
 * Running on http://0.0.0.0:5000
Step 6 — Access Panels
Panel	URL
Login	http://localhost:5000/
Admin	http://localhost:5000/admin
Client	http://localhost:5000/clients
Default owner credentials:

Username: sarker

Password: mimo#123

Master Key: 388401

🔐 Credentials Update Guide
📄 File: .env
Location: Project root

env
# ═══════════════════════════════════════════════════════════
# 🗄 MONGODB — REQUIRED
# ═══════════════════════════════════════════════════════════
MONGO_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
DB_NAME=<your-db-name>

# ═══════════════════════════════════════════════════════════
# 👑 OWNER — REQUIRED (CHANGE ALL 4 VALUES!)
# ═══════════════════════════════════════════════════════════
OWNER_NAME="<your-username>"
OWNER_PASSWORD="<strong-password>"        # ⚠️ use quotes if # is present
OWNER_MASTER_KEY="<random-6-digit-key>"   # Owner login master key
OWNER_KEY="<random-string>"               # URL bypass key (e.g. mm)

# ═══════════════════════════════════════════════════════════
# 📱 TELEGRAM BOT — REQUIRED for log broadcasting
# ═══════════════════════════════════════════════════════════
TELEGRAM_BOT_TOKEN=<from @BotFather>
TELEGRAM_OWNER_IDS=<comma-separated-user-ids>   # Your TG user IDs

# ═══════════════════════════════════════════════════════════
# 💬 DISCORD BOT — REQUIRED for log broadcasting
# ═══════════════════════════════════════════════════════════
DISCORD_BOT_TOKEN=<from Discord Dev Portal>
DISCORD_OWNER_IDS=<comma-separated-user-ids>

# ═══════════════════════════════════════════════════════════
# 🔒 FLASK SECRET — REQUIRED (generate 64-char random)
# ═══════════════════════════════════════════════════════════
SECRET_KEY=<run: python -c "import secrets; print(secrets.token_urlsafe(64))">
PORT=5000
🔑 Credentials Location Map
Credential	File	Line	Description
MongoDB URI	.env	MONGO_URI=	DB connection string
Owner Name	.env	OWNER_NAME=	Owner login username
Owner Password	.env	OWNER_PASSWORD=	Owner login password
Owner Master Key	.env	OWNER_MASTER_KEY=	Owner 6-digit master key
Owner URL Key	.env	OWNER_KEY=	URL bypass key (?key=mm)
Telegram Bot Token	.env	TELEGRAM_BOT_TOKEN=	From @BotFather
Telegram Owner IDs	.env	TELEGRAM_OWNER_IDS=	Your TG user ID(s)
Discord Bot Token	.env	DISCORD_BOT_TOKEN=	From Dev Portal
Discord Owner IDs	.env	DISCORD_OWNER_IDS=	Your Discord user ID(s)
Flask Secret	.env	SECRET_KEY=	Session encryption key
Server Port	.env	PORT=	Default 5000
Default Admin Pass	db.py	Line ~120	admin#123 (change after seed)
📄 File: config.py
Location: Project root

python
# ═══════════════════════════════════════════════════════════
# 🌐 SERVER
# ═══════════════════════════════════════════════════════════
PORT = int(os.getenv("PORT", 5000))
VERSION = "OB55"                    # ⚠️ Change when game updates

# ═══════════════════════════════════════════════════════════
# 🔐 JWT TOKEN SERVERS
# ═══════════════════════════════════════════════════════════
JWT_SERVERS = [
    "https://your-jwt-server-1.com/token",   # ⚠️ UPDATE
    "https://your-jwt-server-2.com/token",
]

# ═══════════════════════════════════════════════════════════
# 🌍 REGIONS
# ═══════════════════════════════════════════════════════════
REGIONS = ["NX", "AG", "IND"]

REGION_CONFIG = {
    "IND": {
        "tokens": "ind_tokens",
        "url": "https://client.ind.freefiremobile.com",
        "state": "IND"
    },
    "NX": {
        "tokens": "nx_tokens",
        "url": "https://client.us.freefiremobile.com",
        "state": "NX"
    },
    "AG": {
        "tokens": "ag_tokens",
        "url": "https://clientbp.ppmainecoonghj.com",
        "state": "AG"
    }
}

# ═══════════════════════════════════════════════════════════
# 🔑 KEY PREFIXES
# ═══════════════════════════════════════════════════════════
API_KEY_PREFIX   = "FF-API"
LIKE_KEY_PREFIX  = "FF-LK"
ADMIN_KEY_PREFIX = "FF-AD"

# ═══════════════════════════════════════════════════════════
# ⚙️ SCHEDULER
# ═══════════════════════════════════════════════════════════
SCHEDULER_HOUR_UTC     = 0            # Daily job
CREDITS_RESET_HOUR_UTC = 0            # Credits reset
EXPIRE_CHECK_INTERVAL  = 300          # 5 min cleanup

# ═══════════════════════════════════════════════════════════
# 🔒 SESSION
# ═══════════════════════════════════════════════════════════
SESSION_TIMEOUT_MINUTES = 60 * 24     # 24h
📄 File: tokens_handler.py
Update JWT token fetch servers (already in config.py)

Ensure JSON files exist for accounts:

text
data/
├── ag_data.json
├── ind_data.json
└── nx_data.json
Format:

json
[
  {"uid": "123456789", "password": "ABCDEF..."},
  {"uid": "987654321", "password": "XYZ123..."}
]
🔄 Update Checklist (Before Deploy)
#	File	What to Change	Why
1	.env	MONGO_URI → prod cluster	DB connection
2	.env	OWNER_NAME, OWNER_PASSWORD, OWNER_MASTER_KEY, OWNER_KEY	Login credentials
3	.env	SECRET_KEY → new 64-char random	Session security
4	.env	TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_IDS	Bot access
5	.env	DISCORD_BOT_TOKEN, DISCORD_OWNER_IDS	Bot access
6	config.py	JWT_SERVERS → your token servers	Token fetch
7	config.py	VERSION = OB55 (current game ver)	Request headers
8	config.py	REGION_CONFIG URLs	Game server hosts
9	data/*.json	Account UIDs + passwords	Token generation
10	db.py	Default admin password (line ~120)	First admin seed
🗄 Database Schema
Collections
Collection	Purpose	Key Index
accounts	Users (owner/admin/user)	name (unique)
api_keys	FF-API + FF-AD keys	key (unique)
like_keys	FF-LK keys	key (unique)
like_usage	Like per-UID-per-day tracker	(key, date)
boost_like	Boost jobs	(uid, created_by) unique
auto_like	Auto jobs	(uid, created_by) unique
activity_logs	All actions	timestamp (desc)
bot_settings	Bot config	key (unique)
{region}_tokens	Access tokens per region	auto
token_state	Token manager state	region
🌐 API Endpoints
Public API
Method	Endpoint	Auth	Purpose
GET	/like?uid=&region=&key=	Key	Send likes
GET	/status?key=	Key	Key status
Auth
Method	Endpoint	Purpose
POST	/auth/login	Login (name + pass + key)
POST	/auth/logout	Logout
GET	/auth/me	Current user
GET	/auth/heartbeat	Session check (3s)
Admin (admin/owner)
Method	Endpoint	Owner-only?
GET	/admin/users	—
POST	/admin/admins/create	✅
DELETE	/admin/users/<name>	—
POST	/admin/users/<name>/status	—
POST	/admin/keys/api/generate	FF-AD only ✅
DELETE	/admin/keys/api/<key>	FF-AD only ✅
POST	/admin/keys/like/generate	—
POST	/admin/boost/create	—
POST	/admin/auto/create	—
GET	/admin/stats	—
GET	/admin/logs	—
POST	/admin/bots/broadcast	—
GET	/admin/scheduler/status	—
Client (user)
Method	Endpoint	Purpose
GET	/client/me	Profile + keys
POST	/client/like	Send like
POST	/client/boost/create	Boost job (API key only)
POST	/client/auto/create	Auto job (API key only)
GET	/client/jobs	My jobs
DELETE	/client/job/<type>/<uid>	Delete job
GET	/client/logs	My activity
👥 User Roles & Permissions
Feature	Owner	Admin	Client (API)	Client (Like)
Login	✅	✅	✅	✅
Send Like (unlimited)	✅	✅ (own key)	✅ (limited)	✅ (limited)
Boost Job	✅	✅	✅	❌
Auto Job	✅	✅	✅	❌
Create Admin	✅	❌	❌	❌
Generate FF-AD	✅	❌	❌	❌
Generate FF-API/LK	✅	✅	❌	❌
Delete FF-AD	✅	❌	❌	❌
View all users	✅	✅	❌	❌
View own logs	✅	✅	✅	✅
Broadcast bot msg	✅	✅	❌	❌
Manage jobs	✅ all	✅ all	✅ own	❌
🔑 Key Types
FF-API-XXXXXX-XXXXXX
Purpose: Subscription API access

Credits: admin-set daily limit (40/day, None=unlimited)

Region lock: ALL / AG / IND / NX

Duration: days from creation

Capabilities: send like, boost, auto

FF-LK-XXXXXX-XXXXXX
Purpose: Subscription Like access

Limit: per-UID per-day (5/UID/day)

Duration: days

Capabilities: send like only

FF-AD-XXXXXX-XXXXXX
Purpose: Admin subscription

Creation: Owner-only

Capabilities: Same as FF-API + admin panel access

🧪 Automation Test
Run Full Test Suite
bash
# 1. Clean DB
python db_cleanup.py --force

# 2. Start server (new terminal)
python main.py

# 3. Run tests (new terminal)
python final_test.py
Test Modes
bash
python final_test.py              # All tests
python final_test.py --valid      # Happy path only
python final_test.py --invalid    # Error cases only
Expected Result
text
  TEST SUMMARY
  ══════════════════════════════════════════════════════
  Passed:  46
  Failed:  0
  Skipped: 0
  Total:   46
  Elapsed: ~64s
Test Coverage
Category	Tests
Auth flows	7
Key generation	5
Role enforcement	4
Client self-register	2
Data isolation	2
Job creation	8
Restrictions	6
Region lock	1
Limits	2
Account suspension	1
Others	8
🚢 Deployment
Option 1 — Vercel
bash
# vercel.json already configured
vercel --prod
Option 2 — Docker
dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "--timeout", "120", "main:app"]
bash
docker build -t fflike-api .
docker run -d --env-file .env -p 5000:5000 fflike-api
Option 3 — VPS (Ubuntu)
bash
# Install
sudo apt update
sudo apt install python3-pip python3-venv nginx

# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Gunicorn service
sudo nano /etc/systemd/system/fflike.service
ini
[Unit]
Description=FF Like API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/project-api-ob55
Environment="PATH=/home/ubuntu/project-api-ob55/venv/bin"
ExecStart=/home/ubuntu/project-api-ob55/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 --timeout 120 main:app
Restart=always

[Install]
WantedBy=multi-user.target
bash
sudo systemctl enable fflike
sudo systemctl start fflike
Nginx reverse proxy:

nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }
}
SSL with Certbot:

bash
sudo certbot --nginx -d your-domain.com
📊 Monitoring
Server Logs
bash
# Real-time
tail -f /var/log/fflike.log

# Filter scheduler
grep "SCHEDULER" /var/log/fflike.log

# Filter token
grep "\[fetch_info\]" /var/log/fflike.log

# Filter bots
grep "\[TG\]\|\[DC\]" /var/log/fflike.log
Admin Panel — Scheduler Status
Navigate to Admin → Dashboard → Scheduler to see:

daily_job — next run 00:00 UTC

cleanup_job — every 5 min

init_pending_jobs — every 15 min

Bot Health
Telegram: /start in bot chat

Discord: !start in server

MongoDB Atlas
Dashboard → Metrics → check connection count

Alerts → set up CPU/Memory alerts

🆘 Troubleshooting
Server won't start
bash
# Check port
netstat -an | grep 5000

# Check Python version
python --version    # Need 3.8+

# Check DB connection
python -c "from db import db; print(db.list_collection_names())"
Like send fails with invalid_account_or_server
Cause: All tokens exhausted for region

Fix:

bash
# Check token count
python -c "from db import db; print(db.ag_tokens.count_documents({}))"

# Restart server (triggers token refresh)
Bot not sending logs
Check 1: Bot token valid?

bash
python -c "from config import TELEGRAM_BOT_TOKEN; print(bool(TELEGRAM_BOT_TOKEN))"
Check 2: Log targets set?

bash
# In Telegram
/setlogs
navigator.clipboard error in browser
Cause: HTTP context (not HTTPS)

Fix: Deploy with HTTPS (SSL) — see Certbot section

Jobs not running
Check:

Scheduler running? → Admin → Dashboard → Scheduler

Key valid? → Check key.expires_at

Credit available? → Check key.used_today < credits_per_day

📜 License
Private project. All rights reserved.

📞 Support
For issues or questions, contact the maintainer.

<div align="center">
Built with 🔥 by sarker

OB55 · v1.0.0 · 46/46 Tests Passing

</div> ```