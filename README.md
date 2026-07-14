# Mental Wellness Chatbot

WhatsApp wellness companion: **FastAPI**, **Meta WhatsApp Cloud API**, **SQLite or Neon Postgres**, optional **Gemini LLM**, **VADER** vent sentiment, **ML** check-in recommender, **5 Indian languages**, timed meditation nudges, daily check-in reminders, and a **Next.js** analytics dashboard on Vercel.

## Architecture

```
WhatsApp user
    → Meta Cloud API webhook (POST /webhook)
    → app.py (signature verify, message_id dedup, PII-safe logs)
    → bot_router.py (state + language preference)
    → handlers (wellness_bot_class, vent_flow, checkin_flow, llm_wellness)
    → SQLite wellness.db  OR  Neon Postgres (DATABASE_URL)
    ← outbound text via whatsapp_cloud.py

Next.js dashboard (Vercel)  ──proxy──►  GET /api/* (api_routes.py)
Streamlit dashboard.py      ──reads──►  wellness.db   # optional local deep dive
```

## Tech stack

| Layer | Technology |
|--------|------------|
| API / webhooks | **FastAPI** + **Uvicorn** |
| WhatsApp | **Meta WhatsApp Cloud API** |
| LLM (optional) | **Gemini** / OpenAI / OpenRouter via `llm_wellness.py` |
| Multilingual | 5 languages — explicit `/language` or menu · `users.preferred_language` |
| Vent mood NLP | **VADER** (`vaderSentiment`) + wellness lexicon tie-break |
| Crisis safety | Phrase list → crisis flags + safe reply flow |
| Check-in ML | **Logistic regression** (scikit-learn) on intensity + category + hour |
| Timed meditation | `meditation_scheduler.py` (asyncio, after **ready**) |
| Daily reminders | `checkin_nudge_scheduler.py` (opt-in `/remind on`) |
| Storage | **SQLite** locally · **Neon Postgres** in production ([docs/NEON.md](docs/NEON.md)) |
| Dashboard | **Next.js** on Vercel ([docs/DASHBOARD.md](docs/DASHBOARD.md)) · Streamlit optional |
| CI | GitHub Actions + **pytest** (74+ tests) |

## Security & secrets

- **Never commit** `.env` or real API keys (see `.env.example`).
- Webhook: verify `META_APP_SECRET` signature when set; dedupe by WhatsApp `message_id`.
- Logs: inbound sender is logged as `hash(phone)` only.
- Dashboard API: set `DASHBOARD_API_KEY` on Render before sharing the Vercel URL.

## Local setup

### 1) Environment

Copy `.env.example` → `.env` and fill in Meta credentials. See [docs/LONG_LIVED_TOKEN.md](docs/LONG_LIVED_TOKEN.md) for a stable Render token.

Optional: set `LLM_PROVIDER=gemini` + `LLM_API_KEY` for AI replies. Leave unset for rule-based fallback.

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

### 4) Dashboard (Next.js — recommended)

```bash
cd dashboard-web
npm install
npm run dev
```

Open http://localhost:3000/login. See [docs/DASHBOARD.md](docs/DASHBOARD.md).

**Streamlit** (optional local view):

```bash
py -m streamlit run dashboard.py
```

### 5) Tests

```bash
py -m pytest -q
py -m pytest tests/test_llm_eval.py -q   # offline LLM safety eval
```

## WhatsApp commands

| Command | Behavior |
|---------|----------|
| `/start` | Welcome + wellness menu (English by default) |
| `/language` | Change language (English, Hindi, Marathi, Gujarati, Bengali) |
| `/checkin` | Multi-step check-in → ML/rules suggestion |
| `/mood 7 note` | Log mood; crisis phrases trigger safety flow |
| `/breathe` | Breathing patterns (buttons or `/breathe calm`) |
| `/meditate` | quick / medium / long → **ready** → timed parts |
| `/affirmation` | Random affirmation (LLM if configured) |
| `/vent` | Multi-turn chat; VADER sentiment + optional LLM |
| `/analyze` | 7-day mood average |
| `/remind on\|off` | Opt in/out of daily check-in nudge |
| `/cancel` | Exit current flow |
| `/help` | Command list |

**Admins** (`ADMIN_NUMBERS`): `/stats`, `/ping`, `/invite` (wa.me link)

### Multilingual (5 languages)

Supported: **English, Hindi, Marathi, Gujarati, Bengali**.

- Default is **English** until the user runs **`/language`** or picks **Language** from the menu.
- **No auto-detect** — stored preference is never overridden by message script.
- **UI shell** (menus, vent intro, breathe, buttons) uses locale bundles in `languages.py`.
- **LLM chat** replies in the user's language via system prompt directive.

Set language: `/language`, `/language hindi`, or menu → Language.

### Meditation flow

1. `/meditate quick` — intro  
2. **ready** — part 1 + auto parts at **+1** and **+2 min** (quick)  
3. **pause** / **resume** / **next** / **end**

Requires an always-on host (e.g. Render) with `ENABLE_MEDITATION_NUDGES=true`.

### Vent / chat flow

1. `/vent` or menu → share text → VADER reply (+ LLM if configured)  
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
bot_router.py               # State machine + language routing
languages.py                # Picker, script detection, UI strings
llm_wellness.py             # Optional Gemini/OpenAI brain
webhook_dedup.py            # WhatsApp message_id deduplication
database.py                 # SQLite + Postgres dual backend
meditation_scheduler.py     # Timed meditation parts
checkin_nudge_scheduler.py  # Daily /remind pushes
whatsapp_cloud.py           # Cloud API send/verify
wellness_bot_class.py       # Command handlers
api_routes.py               # Dashboard metrics API
dashboard-web/              # Next.js dashboard (Vercel)
dashboard.py                # Streamlit (optional)
docs/NEON.md                # Free Postgres setup
docs/DASHBOARD.md           # Vercel dashboard guide
```

## Deploy

| Target | Guide |
|--------|--------|
| Bot (Render) | [DEPLOY.md](DEPLOY.md) |
| DB (Neon, free) | [docs/NEON.md](docs/NEON.md) |
| Dashboard (Vercel) | [docs/DASHBOARD.md](docs/DASHBOARD.md) |

| Blueprint | Purpose |
|-----------|---------|
| [render.yaml](render.yaml) | Bot only (free) |
| [render.with-disk.yaml](render.with-disk.yaml) | Bot + persistent SQLite disk |
| [render.full.yaml](render.full.yaml) | Bot + Streamlit + disk |

**Recommended for beta:** Render free bot + Neon `DATABASE_URL` + Vercel dashboard ≈ **$0/month**.

## Interactive UI

Buttons/lists for language, meditate, breathe, check-in category, vent follow-ups, and main menu after `/start`.

## Roadmap

1. ~~Deploy to Render~~  
2. ~~Interactive buttons / lists~~  
3. ~~Long-lived token guide~~ → [docs/LONG_LIVED_TOKEN.md](docs/LONG_LIVED_TOKEN.md)  
4. ~~Timed meditation pushes~~  
5. ~~Daily check-in reminders (`/remind`)~~  
6. ~~Tests + CI~~  
7. ~~Next.js dashboard on Vercel~~ → [docs/DASHBOARD.md](docs/DASHBOARD.md)  
8. ~~Neon Postgres persistence~~ → [docs/NEON.md](docs/NEON.md)  
9. ~~Optional LLM + eval harness~~ → `llm_wellness.py` + `tests/test_llm_eval.py`  
10. ~~Multilingual (5 Indian languages)~~  
11. Meta **production** access (beyond tester list)  
