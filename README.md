# Mental Wellness Chatbot

WhatsApp wellness companion: **FastAPI**, **Meta WhatsApp Cloud API**, **SQLite**, **VADER** vent sentiment, **ML** check-in recommender, **timed meditation nudges**, optional **daily check-in reminders**, and a **Streamlit** dashboard.

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
| Crisis safety | Phrase list → `vent_logs` + `[crisis]` placeholders |
| Check-in ML | **Logistic regression** (scikit-learn) on intensity + category + hour |
| Timed meditation | `meditation_scheduler.py` (asyncio, after **ready**) |
| Daily reminders | `checkin_nudge_scheduler.py` (opt-in `/remind on`) |
| Storage | **SQLite** (`wellness.db`) |
| Dashboard | **Streamlit** (local or Render via `render.full.yaml`) |
| CI | GitHub Actions + **pytest** |

## Security & secrets

- **Never commit** `.env` or real API keys (see `.env.example`).
- Webhook: verify `META_APP_SECRET` signature when set.
- Logs: inbound sender is logged as `hash(phone)` only.
- `/api/*` is read-only and unauthenticated — add auth before any public dashboard URL.

## Local setup

### 1) Environment

Copy `.env.example` → `.env` and fill in Meta credentials. See [docs/LONG_LIVED_TOKEN.md](docs/LONG_LIVED_TOKEN.md) for a stable Render token.

### 2) Install

```bash
py -m pip install -r requirements.txt
py -m pip install -r requirements-dev.txt   # tests
```

### 3) Run the bot

```bash
py -m uvicorn app:app --port 8000
```

Expose with **ngrok** and set Meta webhook to `https://YOUR-URL/webhook`.

### 4) Dashboard

```bash
py -m streamlit run dashboard.py
```

### 5) Tests

```bash
py -m pytest -q
```

## WhatsApp commands

| Command | Behavior |
|---------|----------|
| `/start` | Welcome + register user + menu |
| `/checkin` | Multi-step check-in → ML/rules suggestion |
| `/mood 7 note` | Log mood; crisis phrases trigger safety flow |
| `/breathe` | Breathing patterns (buttons or `/breathe calm`) |
| `/meditate` | quick / medium / long → **ready** → timed parts |
| `/affirmation` | Random affirmation |
| `/vent` | Multi-turn vent; VADER sentiment |
| `/analyze` | 7-day mood average |
| `/remind on\|off` | Opt in/out of daily check-in nudge |
| `/cancel` | Exit current flow |
| `/help` | Command list |

**Admins** (`ADMIN_NUMBERS`): `/stats`, `/ping`, `/invite` (wa.me link)

### Meditation flow

1. `/meditate quick` — intro  
2. **ready** — part 1 + auto parts at **+1** and **+2 min** (quick)  
3. **pause** / **resume** / **next** / **end**

Requires an always-on host (e.g. Render) with `ENABLE_MEDITATION_NUDGES=true`.

### Vent flow

1. `/vent` → share text → VADER reply + `(Detected tone: …)`  
2. `/done` or buttons to exit  

## Invite a friend (development demo)

1. Add their phone in Meta → WhatsApp → **tester list**.  
2. Set `WHATSAPP_DISPLAY_NUMBER` (digits only) on Render.  
3. Send **`/invite`** as admin, or share `https://wa.me/NUMBER?text=Hi`.  
4. They message the bot and type **`/start`**.

Details: **[DEPLOY.md § Show the chatbot to a new person](DEPLOY.md#show-the-chatbot-to-a-new-person)**

## ML recommender

```bash
py scripts/evaluate_recommender.py
py scripts/seed_demo_data.py
```

## Project layout

```
app.py                      # FastAPI webhook + schedulers
bot_router.py               # State machine
meditation_scheduler.py     # Timed meditation parts
checkin_nudge_scheduler.py  # Daily /remind pushes
whatsapp_cloud.py           # Cloud API send/verify
wellness_bot_class.py       # Command handlers
dashboard.py                # Streamlit
archive/                    # Legacy Flask/Twilio (reference only)
docs/LONG_LIVED_TOKEN.md
```

## Deploy (Render)

| Blueprint | Purpose |
|-----------|---------|
| [render.yaml](render.yaml) | Bot only (free) |
| [render.with-disk.yaml](render.with-disk.yaml) | Bot + persistent DB |
| [render.full.yaml](render.full.yaml) | Bot + Streamlit + disk |
| [render-dashboard.yaml](render-dashboard.yaml) | Streamlit only |

Full guide: **[DEPLOY.md](DEPLOY.md)**

## Interactive UI

Buttons/lists for meditate, breathe, check-in category, vent follow-ups, and main menu after `/start`.

## Roadmap

1. ~~Deploy to Render~~  
2. ~~Interactive buttons / lists~~  
3. ~~Long-lived token guide~~ → [docs/LONG_LIVED_TOKEN.md](docs/LONG_LIVED_TOKEN.md)  
4. ~~Timed meditation pushes~~  
5. ~~Daily check-in reminders (`/remind`)~~  
6. ~~Tests + CI~~  
7. ~~Streamlit on Render~~ → `render.full.yaml`  
8. **React dashboard** consuming `/api/*`  
9. Optional constrained **GenAI** summaries  
10. Meta **production** access (beyond tester list)  
