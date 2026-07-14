# Proactive companion nudges

**Status:** Implemented — morning modes + pattern-gated care pings (opt-in).

## What shipped

| Capability | Behavior |
|------------|----------|
| Morning ritual | `/remind on` — mode `affirmation` · `checkin` · `both` (default) |
| Soft-random timing | Each user gets a sticky `preferred_minute` inside `DAILY_NUDGE_HOUR` + window |
| Care pings | `/care on` — afternoon window when `care_ping_reason()` fires |
| Caps | 1 morning / day; care at most every `CARE_PING_MIN_DAYS` (default 2) |
| Session gate | Skip send if `users.last_seen_at` older than ~23h (WhatsApp free-form rule) |
| Consent | `/remind off` / `/care off` independently |
| Discoverability | Menu: Morning notes · Care pings · Help (+ mentioned on `/start`) |

## Infra constraints (important)

1. **Render free sleep** — the scheduler is a thread *inside* the web process. If the service sleeps, **no outbound pings fire**. Keep it awake with [UptimeRobot](https://uptimerobot.com) (or similar) GETting `/health` every **5–10 min**, or use a paid always-on plan. Cold start (~1 min on “hi”) is the same root cause.
2. **WhatsApp 24h window** — free-form text only works if the user messaged recently. Multi-day “miss you” after true silence needs **Meta message templates** (not built yet).

### Is the 24h limit OK for interview / beta?

**Yes for now.** With a small tester group who talk to the bot at least every day or two, morning notes and care pings work most mornings. Interview demos usually involve live chatting, so the session window stays open.

**Later (production):** Meta WhatsApp **message templates** (approved utility/marketing style) for outbound outside 24h — requires Business verification + template approval. Not needed for beta.

## Env knobs

See `.env.example` / `DEPLOY.md`: `ENABLE_DAILY_CHECKIN_NUDGES`, `DAILY_NUDGE_*`, `ENABLE_CARE_PINGS`, `CARE_PING_*`, `WHATSAPP_SESSION_HOURS`.

## Related files

- `checkin_nudge_scheduler.py` — ticks, prefs, session gate, send
- `patterns.care_ping_reason` — trend / low avg / heavy vent / quiet check-ins
- `llm_wellness.personalized_care_ping` / `personalized_affirmation`
- `bot_router.process_message` — `touch_last_seen`
- `languages.MENU_ROWS` — Morning notes / Care pings / Help
