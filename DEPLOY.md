# Deploy to Render

This guide covers the **WhatsApp bot**, optional **Streamlit dashboard**, tokens, inviting friends, and scheduled features.

## What you get

| Piece | Free tier (`render.yaml`) | With disk (`render.with-disk.yaml` / `render.full.yaml`) |
|--------|---------------------------|-------------------------------------------------------------|
| HTTPS URL for Meta webhook | Yes | Yes |
| SQLite | Ephemeral (resets on **redeploy**) | Persists on 1 GB disk (~$0.25/mo) |
| Backups | On-instance every 24h (`backups/`) | Same + optional nightly **Cron** job |
| Streamlit online | `render-dashboard.yaml` (empty DB unless shared disk) | `render.full.yaml` (bot + dashboard share DB) |
| Cold start | Free service sleeps when idle | Starter plan |

## 1. Push code

Repo must be on GitHub (already synced).

## 2. Create Render service

1. [dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint**
2. Connect **salonic06/Mental-Wellness-Chatbot**
3. Pick a blueprint:
   - **`render.yaml`** — bot only, free-friendly
   - **`render.with-disk.yaml`** — bot + disk + cron backup
   - **`render.full.yaml`** — bot + **Streamlit** + disk (recommended if dashboard should show live data)
   - **`render-dashboard.yaml`** — Streamlit only (second service)
4. Apply blueprint

### Environment variables (Dashboard → your service → Environment)

| Variable | Required | Example |
|----------|----------|---------|
| `WHATSAPP_ACCESS_TOKEN` | Yes | Long-lived token — see [docs/LONG_LIVED_TOKEN.md](docs/LONG_LIVED_TOKEN.md) |
| `WHATSAPP_PHONE_NUMBER_ID` | Yes | Phone number **ID** from API Setup (not the display number) |
| `META_VERIFY_TOKEN` | Yes | Same as local `.env` |
| `META_APP_SECRET` | Yes | App secret (signature verify) |
| `TIMEZONE` | No | `Asia/Kolkata` |
| `ADMIN_NUMBERS` | No | `919422048569` (digits only, comma-separated) |
| `WHATSAPP_DISPLAY_NUMBER` | No | Business phone for **wa.me** links: digits only, e.g. `15551234567` |
| `ENABLE_SCHEDULED_BACKUP` | No | `true` (default in blueprint) |
| `ENABLE_MEDITATION_NUDGES` | No | `true` |
| `ENABLE_DAILY_CHECKIN_NUDGES` | No | `true` on Render blueprint |
| `DAILY_NUDGE_HOUR` | No | `9` (send window starts at this hour in `TIMEZONE`) |
| `DAILY_NUDGE_WINDOW_MINUTES` | No | `30` (only sends in the first N minutes of that hour, e.g. 9:00–9:29 IST) |

Do **not** upload `.env` to git.

## 3. Meta webhook

1. Copy service URL: `https://mental-wellness-bot-xxxx.onrender.com`
2. Meta Developer → WhatsApp → Configuration  
   - **Callback URL:** `https://YOUR-SERVICE.onrender.com/webhook`  
   - **Verify token:** your `META_VERIFY_TOKEN`  
3. Subscribe to **messages**

## 4. Long-lived WhatsApp token

Temporary tokens from API Setup expire in ~24 hours.

**Full step-by-step:** [docs/LONG_LIVED_TOKEN.md](docs/LONG_LIVED_TOKEN.md)

Short version:

1. Meta Business Settings → **System users** → create user → assign WhatsApp + app.
2. **Generate token** with `whatsapp_business_messaging`.
3. Paste into Render as `WHATSAPP_ACCESS_TOKEN`.
4. Renew before expiry (~60 days for many system user tokens).

## 5. Verify

- Browser: `https://YOUR-SERVICE.onrender.com/health` → `{"status":"ok"}`
- WhatsApp: send `/start` to your test number  
- Admin: `/ping` and `/stats` (if your number is in `ADMIN_NUMBERS`)
- Render **Logs** if nothing replies (cold start can take ~30s on free tier)

## Backups

**Free (no disk):**

- App runs `scripts/backup_db.py` on startup and every 24h into `backups/` on the instance  
- Survives **restarts**, not **redeploys**  

**With disk (`render.with-disk.yaml` / `render.full.yaml`):**

- `DATABASE_PATH=/data/wellness.db`, `BACKUP_DIR=/data/backups`  
- Cron job runs daily at 03:00 UTC  

```bash
py scripts/backup_db.py   # manual backup locally
```

## Streamlit on Render

| Blueprint | Use when |
|-----------|----------|
| `render-dashboard.yaml` | Dashboard only; set `DATABASE_PATH` manually if you mount disk |
| `render.full.yaml` | Bot + dashboard share `/data/wellness.db` (best for demos) |

Start command (if creating manually):

```bash
streamlit run dashboard.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true
```

## Local vs Render

| | Local | Render |
|---|--------|--------|
| Bot | `uvicorn app:app` | Same command (auto) |
| Dashboard | `streamlit run dashboard.py` | `render.full.yaml` or local + copied DB |
| Tunnel | ngrok | Render URL |

## Troubleshooting

| Issue | Fix |
|--------|-----|
| Webhook verify fails | URL must end with `/webhook`; token must match |
| 401 on send | Refresh or replace `WHATSAPP_ACCESS_TOKEN` — see long-lived token doc |
| **Bot stops replying after hours** | **Two common causes:** (1) **Free tier sleep** — service spins down after ~15 min idle; Meta webhook may miss the wake window. Fix: [UptimeRobot](https://uptimerobot.com) free monitor pinging `https://YOUR-SERVICE.onrender.com/health` every **10 min**, or upgrade to **Starter**. (2) **Expired token** — temp API Setup tokens die in ~24h; use a **system user long-lived token**. Check `/ping` (admin) or `/health` → `whatsapp.ok`. |
| Slow first message | Free tier waking up — retry after 30s; keep-alive ping helps |
| Empty dashboard on Render | Bot DB is separate unless you use `render.full.yaml` |
| Daily reminder not sent | User must `/remind on`; nudges on; Render awake during **9:00–9:29** (if hour=9, window=30) |
| Nudge at night | Old logic sent any time after 9:00; fixed to morning window only — redeploy latest code |

---

## Show the chatbot to a new person

Meta **development mode** only allows people on your **tester list** (not the general public).

### Step A — Add them as a tester (you, once per friend)

1. [Meta for Developers](https://developers.facebook.com/) → your app → **WhatsApp** → **API Setup**.
2. Under **To** → **Manage phone number list** → **Add phone number**.
3. Enter their full international number (e.g. `91XXXXXXXXXX`, no `+`).
4. They accept the verification code in WhatsApp.

### Step B — Give them a way to open the chat

**Option 1 — wa.me link (easiest)**

1. Set `WHATSAPP_DISPLAY_NUMBER` on Render to your **business test number** (digits only).  
   Find it in API Setup (e.g. `15551234567`).
2. As admin, send `/invite` on WhatsApp — bot replies with a ready-made link.  
   Or build manually:

   ```
   https://wa.me/15551234567?text=Hi
   ```

   Rules: **no `+`**, **no spaces**, country code included.

3. Friend taps the link → WhatsApp opens → they send the pre-filled “Hi” (or any message).

**Option 2 — Add contact manually**

They save your test business number from API Setup and message it like any contact.

### Step C — First message

They type **`/start`** and use **Open menu** or slash commands (`/checkin`, `/vent`, `/meditate quick`, etc.).

### What you maintain

- Render service **live** (free tier may sleep).
- Valid **long-lived token** on Render.
- Tester list updated when adding friends.

### Not in scope for this demo

- Public launch without Meta **production** approval.
- Users not on the tester list cannot message the bot.

---

## Friends demo (summary)

Same as above: testers only, `/start` to begin, `/invite` for wa.me link when `WHATSAPP_DISPLAY_NUMBER` is set.

## Timed meditation nudges

When `ENABLE_MEDITATION_NUDGES=true` (default):

1. `/meditate quick` → type **ready** (part 1 immediately).
2. Auto parts at **+1 min** and **+2 min** after ready (quick session).
3. **pause** / **resume** — resume paces ~1 min per remaining step (no burst).
4. **next** / **end** cancels pending timers.

Requires the web service to stay running. Free-tier sleep may delay nudges.

## Daily check-in reminders

When `ENABLE_DAILY_CHECKIN_NUDGES=true`:

1. User sends **`/remind on`** (opt-in).
2. Once per local day in the morning window (`DAILY_NUDGE_HOUR` + first `DAILY_NUDGE_WINDOW_MINUTES`, default **9:00–9:29** in `TIMEZONE`).
3. **`/remind off`** to stop; **`/remind`** for status.

Disable globally: `ENABLE_DAILY_CHECKIN_NUDGES=false`.

## Admin commands (Cloud API)

Set `ADMIN_NUMBERS` to your WhatsApp digits (same format as stored sender id).

| Command | Purpose |
|---------|---------|
| `/stats` | SQLite usage counts |
| `/ping` | Env vars present? |
| `/invite` | wa.me link + tester instructions |

Legacy Twilio `/checklimit` and `/checkusage` were removed.
