# Phase C — Next.js dashboard (Vercel)

Modern analytics UI for your wellness bot. Reads **aggregated** data only — mood scores, check-in topics, vent *tone buckets*. No private message text.

## Architecture

```
WhatsApp bot (Render)          Next.js dashboard (Vercel)
FastAPI /api/*  ◄── HTTPS ────  dashboard-web/
SQLite wellness.db              Charts + pattern insights
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

## API endpoints

| Route | Data |
|-------|------|
| `GET /api/metrics/summary` | Totals, avg mood |
| `GET /api/metrics/mood-trends` | Daily mood series |
| `GET /api/metrics/checkin-categories` | Topic breakdown |
| `GET /api/vent/sentiment-summary` | Tone buckets (no text) |
| `GET /api/patterns/insights` | Pattern lines |

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
