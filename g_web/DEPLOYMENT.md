# Deployment Guide

**Important:** the site needs a host that can run Python (`server.py`).
Netlify, Vercel and GitHub Pages only host static files, so the menu, bookings and
admin panel would **not** work there. Use one of the options below.

## Option A – Render (recommended, about $7/month)

1. Create a GitHub account (in the restaurant's name) and a **private** repository.
   Upload every file in this folder to it (the `.gitignore` keeps secrets out).
2. Create an account at https://render.com → **New + → Blueprint** → choose the repository.
   Render reads `render.yaml` and sets up the server plus a 1 GB persistent disk automatically.
3. When asked, type the **ADMIN_PASSWORD** (long and unique). Fill in the notification
   settings from step "Notifications" below (optional but strongly recommended).
4. Click **Apply**. After 2–3 minutes you get a URL such as
   `https://lala-restaurant.onrender.com`.
5. Test: open `/`, place a test booking, open `/admin.html`, log in, and confirm the booking appears.

> The disk is what keeps bookings and menu edits safe. Without a disk (free plan),
> **all data is erased whenever the server restarts.** Do not use the free plan for a real restaurant.

## Option B – Railway / Fly.io / any VPS (Docker)

The included `Dockerfile` works on any Docker host.
Mount a persistent volume at `/data`, then set the environment variables from `.env.example`.

```bash
docker build -t lala .
docker run -d -p 80:8000 -v lala-data:/data \
  -e ADMIN_PASSWORD='your-strong-password' -e SECRET_KEY='long-random-string' lala
```

Put Caddy or Nginx in front of it for HTTPS if you run it on a raw VPS.

## Custom domain (e.g. sulthansbriyani.in)

1. Buy the domain in the **restaurant's** name (GoDaddy, Namecheap, BigRock, etc.).
2. Render → your service → **Settings → Custom Domains → Add**. Render shows the DNS records.
3. Add those records at the domain registrar. HTTPS is issued automatically within minutes.

## Notifications (get a message on every new booking)

Set any of these environment variables. Telegram is the most reliable and free.

**Telegram**
1. In Telegram, message **@BotFather** → `/newbot` → copy the token → `TELEGRAM_BOT_TOKEN`.
2. Send any message to your new bot from the owner's phone.
3. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser; copy the number in `"chat":{"id":...}` → `TELEGRAM_CHAT_ID`.

**Email (Gmail):** turn on 2-step verification, create an *App Password*, then set
`SMTP_USER` (Gmail address), `SMTP_PASS` (app password), `NOTIFY_EMAIL_TO` (where alerts go).

**WhatsApp:** CallMeBot is a free personal-use service. Register the owner's number at
https://www.callmebot.com, then set `CALLMEBOT_PHONE` (with country code, e.g. `919876543210`) and
`CALLMEBOT_APIKEY`. For a busy restaurant, consider the official WhatsApp Business Cloud API later.

## After going live – checklist

- [ ] Replace demo phone/address/hours in **Admin → Store Settings**
- [ ] Replace sample dishes and photos in **Admin → Menu**
- [ ] Test a booking and confirm the notification arrives
- [ ] Log in to admin from the owner's phone
- [ ] Download a CSV export once, to confirm it works
- [ ] Save the admin password in the owner's password manager

## Backups

The server writes a daily backup into a `backups/` folder next to the database (last 14 kept).
Because that folder lives on the same disk, also ask the owner to press **Export CSV** in the admin
panel about once a week and keep the file in Google Drive.
