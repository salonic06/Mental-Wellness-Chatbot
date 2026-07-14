# Neon Postgres (free persistent database)

Use Neon when you want **$0/month persistent storage** instead of Render disk (~$7/mo).

## Why Neon over Supabase free?

| | Neon free | Supabase free |
|--|-----------|---------------|
| Cost | $0, no card | $0 |
| Storage | 0.5 GB | 500 MB |
| Pauses when idle | Scales to zero (~1–2s wake) | **Full project pause after 7 days** |
| Good for this bot | ✅ | ❌ (bot goes offline silently) |

## Setup (your steps — ~15 min)

### 1. Create Neon project

1. Go to [neon.tech](https://neon.tech) → sign up (no credit card).
2. **New project** → name it e.g. `wellness-bot`.
3. Copy the **pooled** connection string (starts with `postgresql://`).

It looks like:

```
postgresql://user:password@ep-xxxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
```

### 2. Add to Render

Render → your bot service → **Environment**:

| Variable | Value |
|----------|--------|
| `DATABASE_URL` | paste Neon pooled connection string |

You do **not** need `DATABASE_PATH` when `DATABASE_URL` is set.

**Manual deploy** (or push to GitHub if auto-deploy is on).

On first boot the bot creates all tables automatically (including `users.preferred_language` for multilingual support).

If you created the Neon database **before** the multilingual update, run once in the Neon SQL editor:

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_language TEXT;
```

### 3. Verify

- Render logs: `Database initialized (postgres, postgres://...)`
- WhatsApp: send `/start`, then `/checkin`
- Admin: `/stats` — should show counts > 0
- Dashboard: **Refresh** — storage shows as postgres

### 4. Keep Render free tier (optional)

- Render web = **free** (may sleep)
- Neon DB = **free** (persists data)
- UptimeRobot ping `/health` every **5–10 min** → keeps Render awake so morning/care pings can fire (required for proactive outbound)

Total cost: **$0**.

## Local dev

Leave `DATABASE_URL` unset → uses local `wellness.db` (SQLite). No Neon account needed for development.

To test against Neon locally, add `DATABASE_URL` to your `.env`.

## Limits (10–15 users)

Neon free: 0.5 GB storage, 100 compute-hours/month — more than enough for a small wellness group.

If Neon compute hours run out, DB pauses until next month (rare at this scale).

## Rollback

Remove `DATABASE_URL` from Render → bot falls back to ephemeral SQLite on the instance.
