# Deploy to Render

Streamlit stays **local** for now. This guide deploys only the **WhatsApp bot** (`app.py`).

## What you get

| Piece | Free tier (`render.yaml`) | With disk (`render.with-disk.yaml`) |
|--------|---------------------------|-------------------------------------|
| HTTPS URL for Meta webhook | Yes | Yes |
| SQLite | Ephemeral (resets on **redeploy**) | Persists on 1 GB disk (~$0.25/mo) |
| Backups | On-instance every 24h (`backups/`) | Same + optional nightly **Cron** job |
| Cold start | Free service sleeps when idle | Starter plan |

## 1. Push code

Repo must be on GitHub (already synced).

## 2. Create Render service

1. [dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint**
2. Connect **salonic06/Mental-Wellness-Chatbot**
3. Pick **`render.yaml`** (free-friendly) or **`render.with-disk.yaml`** (paid disk + cron)
4. Apply blueprint

### Environment variables (Dashboard → your service → Environment)

| Variable | Required | Example |
|----------|----------|---------|
| `WHATSAPP_ACCESS_TOKEN` | Yes | From Meta → WhatsApp → API setup |
| `WHATSAPP_PHONE_NUMBER_ID` | Yes | Phone number ID |
| `META_VERIFY_TOKEN` | Yes | Same as local `.env` |
| `META_APP_SECRET` | Yes | App secret (signature verify) |
| `TIMEZONE` | No | `Asia/Kolkata` |
| `ADMIN_NUMBERS` | No | `919422048569` |
| `ENABLE_SCHEDULED_BACKUP` | No | `true` (default in blueprint) |

Do **not** upload `.env` to git.

## 3. Meta webhook

1. Copy service URL: `https://mental-wellness-bot-xxxx.onrender.com`
2. Meta Developer → WhatsApp → Configuration  
   - **Callback URL:** `https://YOUR-SERVICE.onrender.com/webhook`  
   - **Verify token:** your `META_VERIFY_TOKEN`  
3. Subscribe to **messages**

## 4. WhatsApp token on Render

Temporary Meta tokens expire (~24h). For a stable demo:

- Create a **System User** + **long-lived token** in Meta Business settings, or  
- Refresh `WHATSAPP_ACCESS_TOKEN` in Render when messages fail with 401

## 5. Verify

- Browser: `https://YOUR-SERVICE.onrender.com/health` → `{"status":"ok"}`
- WhatsApp: send `/start` to your test number  
- Render **Logs** if nothing replies (cold start can take ~30s on free tier)

## Backups

**Free (no disk):**

- App runs `scripts/backup_db.py` on startup and every 24h into `backups/` on the instance  
- Survives **restarts**, not **redeploys**  
- Periodically download DB from your machine if you care about production data:

  ```bash
  py scripts/backup_db.py
  ```

**With disk (`render.with-disk.yaml`):**

- Set `DATABASE_PATH=/data/wellness.db`, `BACKUP_DIR=/data/backups`  
- Cron job runs daily at 03:00 UTC  
- DB + backups survive redeploys

## Local vs Render

| | Local | Render |
|---|--------|--------|
| Bot | `uvicorn app:app` | Same command (auto) |
| Dashboard | `streamlit run dashboard.py` | Keep local; point at copied `wellness.db` or use `/api/*` later |
| Tunnel | ngrok | Render URL |

## Optional: second service (Streamlit later)

New **Web Service**, same repo:

- **Start command:** `streamlit run dashboard.py --server.port=$PORT --server.address=0.0.0.0`  
- Mount same disk or use Postgres when you outgrow SQLite

## Troubleshooting

| Issue | Fix |
|--------|-----|
| Webhook verify fails | URL must end with `/webhook`; token must match |
| 401 on send | Refresh `WHATSAPP_ACCESS_TOKEN` |
| Slow first message | Free tier waking up — retry after 30s |
| Empty dashboard locally | Render DB is separate; copy backup or re-seed demo data |

---

## Friends demo (development only)

This project is scoped as a **development / friends demo**, not public production.

### Add a friend as a tester

1. [Meta for Developers](https://developers.facebook.com/) → your app → **WhatsApp** → **API Setup** (or **Configuration**).
2. Under **To** / **Phone numbers** → **Manage phone number list** → **Add phone number**.
3. Enter their full international number (e.g. `91XXXXXXXXXX`).
4. They complete the verification code in WhatsApp.
5. They message your **test business number** (shown in API Setup, e.g. `+1 555 …`).

### What friends should do

- Send `/start` → tap **Open menu** for buttons/lists.
- Or use slash commands (`/checkin`, `/vent`, `/help`) as before.

### What you maintain

- Render service stays **live** (free tier may sleep — first reply can be slow).
- Refresh **WHATSAPP_ACCESS_TOKEN** in Render when Meta returns 401 (~24h tokens).
- Optional: share `https://wa.me/PHONE_NUMBER` link (digits only, no `+`) after they are added as testers.

### Not in scope for this demo

- Public launch without Meta **production** approval and Business Verification.
- Serving unknown users who are not on the tester list.

See roadmap: **long-lived token** and **production access** are planned for later if you outgrow the tester list.
