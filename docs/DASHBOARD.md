# Phase C — Next.js dashboard (Vercel)

Modern analytics UI for your wellness bot. Reads **aggregated** data only — mood scores, check-in topics, vent *tone buckets*. No private message text.

## Architecture

```
WhatsApp bot (Render)          Next.js dashboard (Vercel)
FastAPI /api/*  ◄── proxy ────  dashboard-web/
SQLite or Neon Postgres         Aggregated charts + beta snapshot
```

## 1. Secure the bot API (Render)

In Render → **Environment**:

| Variable | Example |
|----------|---------|
| `DASHBOARD_API_KEY` | long random string (e.g. `openssl rand -hex 32`) |
| `DASHBOARD_CORS_ORIGINS` | `https://your-app.vercel.app` |

Redeploy the bot after setting these.

## 2. Deploy dashboard to Vercel

1. Push this repo to GitHub.
2. [vercel.com](https://vercel.com) → **Add New Project** → import repo.
3. Set **Root Directory** to `dashboard-web`.
4. **Required** environment variable:
   - `NEXT_PUBLIC_API_URL` = `https://your-bot.onrender.com`
5. Deploy.

The dashboard uses a **server-side proxy** (`/api/proxy/*`) — the browser never calls Render directly, so CORS is not an issue.

## 3. Sign in

Open your Vercel URL → enter **Dashboard API key** only (same as `DASHBOARD_API_KEY` on Render).

The bot URL comes from `NEXT_PUBLIC_API_URL` on Vercel — you don't type it at login.

## 4. Local dev

Terminal 1 — bot:

```bash
py -m uvicorn app:app --port 8000
```

Terminal 2 — dashboard:

```bash
cd dashboard-web
npm install
npm run dev
```

Open http://localhost:3000/login (leave API key empty if `DASHBOARD_API_KEY` unset locally).

## What the UI shows (interview-friendly)

Designed for **aggregated, anonymous** beta demos — no phone numbers or message text.

| Section | What it proves |
|---------|----------------|
| **7 / 30 / 90 day range** | You can slice trends for beta reviews |
| **Beta snapshot** | Registered users, active users, events, avg mood in one line |
| **Daily activity chart** | Combined check-ins + mood + chat tone entries per day |
| **Metric cards** | Users, check-ins, chat sessions, events in range |
| **Mood over time** | Daily average mood series |
| **Conversation tone** | VADER sentiment buckets only |
| **Check-in topics** | Category counts |
| **Pattern insights** | Rule-based lines + crisis flag count |

## API endpoints

| Route | Data |
|-------|------|
| `GET /api/metrics/summary` | Totals, storage type (sqlite/postgres/ephemeral) |
| `GET /api/metrics/mood-trends?days=30` | Daily mood series |
| `GET /api/metrics/activity-trends?days=30` | Daily events + active users |
| `GET /api/metrics/checkin-categories` | Topic breakdown |
| `GET /api/vent/sentiment-summary?days=30` | Tone buckets (no text) |
| `GET /api/patterns/insights?days=30` | Pattern lines + avg mood |

All require header `X-Dashboard-Key` when `DASHBOARD_API_KEY` is set.

## LLM eval harness

Offline safety checks for vent replies:

```bash
py llm_eval_harness.py   # structural only
py scripts/llm_eval.py   # + live LLM if configured
py -m pytest tests/test_llm_eval.py -q
```

## Privacy

- Vent logs store **sentiment bucket + word count**, not message content.
- Dashboard never shows phone numbers or notes in Phase C API.
- Streamlit `dashboard.py` remains for local deep dives; use Vercel UI for a modern shareable view.

## Empty dashboard / zeros after chatting

Two common causes:

1. **Render free tier (ephemeral DB)** — no `DATABASE_URL` set. Fix: [docs/NEON.md](NEON.md) (free) or `render.with-disk.yaml` (~$7/mo).

2. **What you log depends on how you chat** — casual free-text fills **Conversation tone** (`vent_logs`). **Mood over time** and **Check-in topics** need `/checkin` or `/mood 7 optional note`.

After switching to persistent disk, send a `/checkin` on WhatsApp, then click **Refresh** on the dashboard.

## Dashboard still looks like the old UI?

The v2 layout (7/30/90d pills, **Beta snapshot**, **Daily activity** chart) lives in `dashboard-web/`. Vercel must deploy from commit `19242f4` or later with **Root Directory** = `dashboard-web`.

1. Vercel → your project → **Deployments** → confirm latest commit hash.
2. If stale, **Redeploy** (or push a new commit).
3. Hard refresh the browser (Ctrl+Shift+R). Footer should show **Dashboard v2**.

## Duplicate WhatsApp replies

Meta retries webhooks when the server is slow or waking from sleep. The bot deduplicates by WhatsApp `message_id` so each user message is processed once. Redeploy after pulling the latest code if you still see triple replies.
