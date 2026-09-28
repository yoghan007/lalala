# LALA RESTAURANT (Sulthans Briyani) – Website + Admin Panel

A complete restaurant website with a live admin panel, online reservations/orders,
instant owner notifications, and automatic daily backups.

## What is in this package

| File | Purpose |
|---|---|
| `index.html` | Public customer website |
| `admin.html` | Password-protected owner control panel (`/admin.html`) |
| `server.py` | Backend + API + web server (Python standard library only) |
| `restaurant.db` | Created automatically on first start (menu, settings, bookings) |
| `.env.example` | List of settings to enter on your hosting dashboard |
| `render.yaml`, `Dockerfile` | Ready-made deployment files |
| `OWNER_GUIDE.md` | Day-to-day guide for the restaurant owner |
| `DEPLOYMENT.md` | Step-by-step guide to put it online |

## Run on your own computer

```bash
# Windows PowerShell:  $env:ADMIN_PASSWORD="mypassword"
export ADMIN_PASSWORD="mypassword"
python server.py
```
Open `http://localhost:8000` (website) and `http://localhost:8000/admin.html` (admin).
Requires Python 3.9+. No `pip install` needed.

## Security built in
- Admin login with rate-limited password attempts and 12-hour sessions
- All admin actions (view bookings, edit menu/settings) require login
- Server code and database files can never be downloaded through the website
- Input validation on all forms, booking spam limit per visitor
- Daily automatic database backup (last 14 kept) + one-click CSV export of bookings
