# Mental Wellness Chatbot

WhatsApp wellness companion: **FastAPI**, **Meta WhatsApp Cloud API**, **SQLite**, **VADER** vent sentiment, **ML** check-in recommender, and a **Streamlit** dashboard.

## Architecture

```
WhatsApp user
    → Meta Cloud API webhook (POST /webhook)
    → app.py (signature verify, PII-safe logs)
    → bot_router.py (state: initial | venting | meditation_choose | meditating | checkin_*)
    → handlers (wellness_bot_class, vent_flow, checkin_flow, sentiment_nlp)
    → SQLite wellness.db
    ← outbound text via whatsapp_cloud.py

Streamlit dashboard.py  ──reads──►  wellness.db
GET /api/* (api_routes.py)  ──reads──►  wellness.db   # for future React UI
```

## Tech stack

| Layer | Technology |
|--------|------------|
| API / webhooks | **FastAPI** + **Uvicorn** |
| WhatsApp | **Meta WhatsApp Cloud API** |
| Vent mood NLP | **VADER** (`vaderSentiment`) + wellness lexicon tie-break |
| Crisis safety | Phrase list → `vent_logs` + `[crisis]` placeholders in mood/check-in tables |
| Check-in ML | **Logistic regression** (scikit-learn) on intensity + category + hour |
| Storage | **SQLite** (`wellness.db`) |
| Dashboard | **Streamlit** |
| Legacy (unused) | Flask + Twilio (`mental_wellness.py`) |

## Security & secrets

- **Never commit** `.env` or real API keys (see `.env.example`).
- `config.json` in the repo contains **non-secret** defaults only (`timezone`). Use `config.example.json` as a template for optional legacy keys.
- Webhook: verify `META_APP_SECRET` signature when set.
- Logs: inbound sender is logged as `hash(phone)` only.
- `/api/*` endpoints are **read-only** and unauthenticated — fine for local demo; add auth before any public deploy.

## Local setup

### 1) Environment

Copy `.env.example` → `.env` and fill in:

```env
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
META_VERIFY_TOKEN=wellness-bot-dev-123
META_APP_SECRET=...
TIMEZONE=Asia/Kolkata
ADMIN_NUMBERS=          # optional, comma-separated E.164
```

### 2) Install

```bash
py -m pip install -r requirements.txt
```

### 3) Run the bot

```bash
py -m uvicorn app:app --port 8000
```

Expose with **ngrok** and set Meta webhook to `https://YOUR-URL/webhook` (include `/webhook`).

### 4) Dashboard

```bash
py -m streamlit run dashboard.py
```

### 5) REST API (optional)

With the server running:

- `GET /health` — liveness
- `GET /api/health` — API + DB presence
- `GET /api/metrics/summary` — counts for dashboard/React
- `GET /api/mood-logs?limit=50`
- `GET /api/checkins?limit=50`
- `GET /api/vent-logs?limit=50`

## WhatsApp commands

| Command | Behavior |
|---------|----------|
| `/start` | Welcome + register user |
| `/checkin` | Multi-step check-in → ML/rules suggestion |
| `/mood 7 note` | Log mood; crisis phrases in note trigger safety flow |
| `/breathe` | List patterns; `/breathe calm` etc. for timings |
| `/meditate` | List durations; `/meditate quick` → stepwise session |
| `/affirmation` | Random affirmation |
| `/vent` | Multi-turn vent; VADER sentiment; slash commands allowed |
| `/analyze` | 7-day mood average |
| `/cancel` | Exit current flow |
| `/help` | Command list |

### Meditation flow

1. `/meditate quick` (or medium / long) — intro (part 1 of N)
2. `ready` — begin timed **parts** (user-paced; type `next` between segments)
3. `next` — next script segment (~minute gaps suggested from `meditations.json`)
4. `pause` / `resume` / `status` / `end`

WhatsApp cannot push mid-session timers reliably on a laptop demo without a always-on worker; pacing is **user-driven** with suggested minute gaps (honest for interviews).

### Vent flow

1. `/vent` — listen mode
2. Free text — VADER → bucket reply + `(Detected tone: …)`
3. Optional `/breathe`, `/mood`, `/affirmation`, `/meditate` during vent
4. `/done` or `/cancel` to exit

## ML recommender

- Rules baseline after every `/checkin`
- Trains when **12+** check-ins exist

```bash
py scripts/evaluate_recommender.py
py scripts/seed_demo_data.py    # optional demo users 9199000000XX
```

Report: `reports/recommender_evaluation.md`

## Project layout

```
app.py                 # FastAPI webhook + API router
api_routes.py          # Read-only /api metrics
whatsapp_cloud.py      # Send + signature verify
bot_router.py          # State machine + command dispatch
vent_flow.py           # Multi-turn /vent
sentiment_nlp.py       # VADER + crisis (single NLP module)
checkin_flow.py        # Guided /checkin
recommender.py         # ML + rules
wellness_bot_class.py  # Command handlers
database.py            # Schema + migrations
state_store.py         # Conversation state in SQLite
dashboard.py           # Streamlit analytics
mental_wellness.py     # Legacy Flask/Twilio
```

## Roadmap

1. **Deploy** (Render/Railway) + long-lived WhatsApp token  
2. **React dashboard** consuming `/api/*`  
3. WhatsApp **interactive buttons** (lists/buttons)  
4. Optional constrained **GenAI** summaries (safety-reviewed)  
