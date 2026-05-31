# Long-lived WhatsApp access token

Temporary tokens from **Meta → WhatsApp → API Setup** expire in about **24 hours**. For a Render demo that stays up without daily paste-ins, create a **System User** token (typically 60 days, renewable) or a permanent token tied to your Business portfolio.

## Prerequisites

- [Meta Business Suite](https://business.facebook.com/) linked to your WhatsApp app
- Your app added under **Business Settings → Accounts → Apps**
- WhatsApp product enabled on the app with a test or production number

## Option A — System User token (recommended for demos)

1. Open [Business Settings](https://business.facebook.com/settings) → **Users** → **System users**.
2. **Add** a system user (e.g. `wellness-bot-render`), role **Admin** or **Employee** with WhatsApp permissions.
3. **Assign assets**: WhatsApp Business Account + your Meta app.
4. Click the system user → **Generate new token**.
5. Select your app and permissions at minimum:
   - `whatsapp_business_messaging`
   - `whatsapp_business_management` (optional, for number management)
6. Copy the token once — it is shown only once.
7. In **Render** → your web service → **Environment** → set:
   - `WHATSAPP_ACCESS_TOKEN` = pasted token
8. Redeploy or wait for the next instance restart.

### Renew before expiry

System User tokens often last **60 days**. Set a calendar reminder. Generate a new token and update Render the same way.

## Option B — Extend a short-lived user token (Graph API Explorer)

Useful for local dev only; still not ideal for production.

1. [Graph API Explorer](https://developers.facebook.com/tools/explorer/) → select your app → **Generate access token** with `whatsapp_business_messaging`.
2. Exchange for long-lived token:

   ```http
   GET https://graph.facebook.com/v22.0/oauth/access_token
     ?grant_type=fb_exchange_token
     &client_id=YOUR_APP_ID
     &client_secret=YOUR_APP_SECRET
     &fb_exchange_token=SHORT_LIVED_TOKEN
   ```

3. Put the `access_token` from the response into `WHATSAPP_ACCESS_TOKEN`.

## Verify the token works

```bash
curl -s "https://graph.facebook.com/v22.0/me?access_token=YOUR_TOKEN"
```

Or send `/start` on WhatsApp and check Render logs for `401` / `OAuthException`.

## Security

- Never commit tokens to git.
- Rotate if leaked.
- Restrict System User permissions to only what the bot needs.

## Related env vars

| Variable | Purpose |
|----------|---------|
| `WHATSAPP_ACCESS_TOKEN` | Bearer token for sending messages |
| `WHATSAPP_PHONE_NUMBER_ID` | Numeric ID from API Setup (not the display phone) |
| `META_APP_SECRET` | Webhook signature verification |

See also [DEPLOY.md](../DEPLOY.md) and [.env.example](../.env.example).
