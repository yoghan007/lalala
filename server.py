#!/usr/bin/env python3
"""
LALA RESTAURANT (Sulthans Briyani) - website + API server.

Standard library only (no pip packages needed).
All settings come from environment variables - see .env.example.
"""
import csv
import hmac
import hashlib
import io
import json
import logging
import os
import re
import secrets
import smtplib
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
from contextlib import closing
from datetime import datetime
from email.message import EmailMessage
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("lala")

# --------------------------------------------------------------------------
# Configuration (environment variables)
# --------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "restaurant.db"))
PORT = int(os.environ.get("PORT", "8000"))
HOST = os.environ.get("HOST", "0.0.0.0")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "").strip()  # only if frontend is on another domain
TRUST_PROXY = os.environ.get("TRUST_PROXY", "1") == "1"        # Render/Railway/Fly sit behind a proxy

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not ADMIN_PASSWORD:
    ADMIN_PASSWORD = secrets.token_urlsafe(9)
    log.warning("ADMIN_PASSWORD not set. Temporary password for this run: %s", ADMIN_PASSWORD)
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    log.warning("SECRET_KEY not set. Admin logins will reset on every restart.")
TOKEN_TTL = 12 * 3600  # admin session length: 12 hours

# Notification channels (all optional - configure any you like)
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)
NOTIFY_EMAIL_TO = os.environ.get("NOTIFY_EMAIL_TO", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
CALLMEBOT_PHONE = os.environ.get("CALLMEBOT_PHONE", "")    # WhatsApp via CallMeBot, e.g. 919876543210
CALLMEBOT_APIKEY = os.environ.get("CALLMEBOT_APIKEY", "")

# --------------------------------------------------------------------------
# Default content (seeded on first run only)
# --------------------------------------------------------------------------
DEFAULT_SETTINGS = {
    "announcement_enabled": "true",
    "announcement_text": "🔥 Today's Special: Free Royal Falooda with every Bucket Briyani order! Call 1234567890 to order.",
    "is_open": "true",
    "opening_hours": "11:00 AM – 10:30 PM",
    "phone": "1234567890",
    "address": "88/71 B, Majeeth Rd, Aranmanai Vaasal, Sivaganga, TN 630561",
    "plus_code": "VF3Q+4X",
    "delivery_radius": "5 km Free Delivery in Sivaganga",
    "whatsapp": "1234567890",
    "instagram": "https://instagram.com",
    "facebook": "https://facebook.com",
}

DEFAULT_MENU = [
    ("Sulthans Special Mutton Briyani", "biryani", "240", "Seeraga Samba rice layered with succulent tender mutton pieces, cooked over low flame with traditional Sulthans spice mix.", "Chef Special", "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?q=80&w=800&auto=format&fit=crop"),
    ("Sulthans Chicken Briyani", "biryani", "180", "Aromatic, long-grain spiced rice layered with soft, juicy chicken marinated in yogurt and secret ground spices.", "Bestseller", "https://images.unsplash.com/photo-1633945274405-b6c8069047b0?q=80&w=800&auto=format&fit=crop"),
    ("Flaky Malabar Parotta", "breads", "25", "Multi-layered, flaky, golden-crisp parotta hand-rolled and cooked on a hot tawa with pure ghee.", "Hot Favorite", "https://images.unsplash.com/photo-1626777552726-4a6b54c97e46?q=80&w=800&auto=format&fit=crop"),
    ("Stuffed Aloo Parotta", "breads", "60", "Wholesome wheat bread stuffed with seasoned mashed potatoes, herbs, and mild green chillies, served hot with butter.", "Customer Pick", "https://images.unsplash.com/photo-1601050690597-df0568f70950?q=80&w=800&auto=format&fit=crop"),
    ("Special Ifthar Box", "breads", "220", "Complete festive combo including Chicken Biryani, Dates, Samosa, Fresh Fruit Juice, Water Bottle & Sweet dish.", "Special Meal Box", "https://images.unsplash.com/photo-1541518763669-27fef04b14da?q=80&w=800&auto=format&fit=crop"),
    ("Pepper Mutton Chukka", "sides", "260", "Tender mutton chunks dry-roasted with freshly crushed black pepper, curry leaves, and small shallots.", "Spicy Favorite", "https://images.unsplash.com/photo-1544025162-d76694265947?q=80&w=800&auto=format&fit=crop"),
    ("Crisp Tawa Fish Fry", "sides", "190", "Fresh catch coated in traditional Chettinad spicy red masala and shallow fried to crispy perfection.", "Seafood Special", "https://images.unsplash.com/photo-1534939561126-855b8675edd7?q=80&w=800&auto=format&fit=crop"),
    ("Royal Falooda Delight", "desserts", "110", "Layered rose syrup, falooda noodles, basil seeds, rich ice cream, chopped nuts, and Tutti Frutti.", "Must Try Dessert", "https://images.unsplash.com/photo-1572490122747-3968b75cc699?q=80&w=800&auto=format&fit=crop"),
    ("Special Kulhad Kheer", "desserts", "70", "Rich saffron and cardamom milk pudding served chilled in traditional clay pot with roasted almonds.", "Sweet Special", "https://images.unsplash.com/photo-1541781774459-bb2af2f05b55?q=80&w=800&auto=format&fit=crop"),
]

STATUSES = {"Pending", "Confirmed", "Completed", "Cancelled"}
STATIC_EXT = {".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".woff", ".woff2"}
MAX_BODY = 20_000


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
def db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(os.path.abspath(DB_FILE)), exist_ok=True)
    with closing(db()) as conn, conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, phone TEXT NOT NULL, request_type TEXT NOT NULL,
            guest_count TEXT, preferred_date TEXT, preferred_time TEXT, special_notes TEXT,
            status TEXT DEFAULT 'Pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("""CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, category TEXT NOT NULL, price TEXT NOT NULL,
            description TEXT, badge TEXT, image_url TEXT, is_active INTEGER DEFAULT 1)""")
        if conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0:
            conn.executemany("INSERT INTO settings (key, value) VALUES (?, ?)", list(DEFAULT_SETTINGS.items()))
            log.info("Default settings seeded")
        if conn.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO menu_items (name, category, price, description, badge, image_url, is_active) VALUES (?,?,?,?,?,?,1)",
                DEFAULT_MENU)
            log.info("Default menu seeded")
    log.info("Database ready at %s", DB_FILE)


def do_backup(keep=14):
    folder = os.path.join(os.path.dirname(os.path.abspath(DB_FILE)), "backups")
    os.makedirs(folder, exist_ok=True)
    target = os.path.join(folder, "restaurant-%s.db" % datetime.now().strftime("%Y%m%d"))
    with closing(sqlite3.connect(DB_FILE)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)
    for old in sorted(f for f in os.listdir(folder) if f.endswith(".db"))[:-keep]:
        os.remove(os.path.join(folder, old))


def backup_loop():
    while True:
        try:
            do_backup()
        except Exception as exc:  # never crash the server because of a backup
            log.warning("Backup failed: %s", exc)
        time.sleep(24 * 3600)


# --------------------------------------------------------------------------
# Auth + rate limiting
# --------------------------------------------------------------------------
def make_token():
    exp = str(int(time.time()) + TOKEN_TTL)
    sig = hmac.new(SECRET_KEY.encode(), exp.encode(), hashlib.sha256).hexdigest()
    return "%s.%s" % (exp, sig)


def valid_token(token):
    try:
        exp, sig = token.split(".", 1)
        good = hmac.new(SECRET_KEY.encode(), exp.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, good) and int(exp) > time.time()
    except (ValueError, AttributeError):
        return False


class RateLimiter:
    def __init__(self, limit, window):
        self.limit, self.window = limit, window
        self.hits, self.lock = {}, threading.Lock()

    def _recent(self, key):
        cutoff = time.time() - self.window
        recent = [t for t in self.hits.get(key, []) if t > cutoff]
        if recent:
            self.hits[key] = recent
        else:
            self.hits.pop(key, None)
        return recent

    def blocked(self, key):
        with self.lock:
            return len(self._recent(key)) >= self.limit

    def add(self, key):
        with self.lock:
            self._recent(key)
            self.hits.setdefault(key, []).append(time.time())


login_fails = RateLimiter(limit=5, window=300)        # 5 wrong passwords / 5 min / IP
booking_limit = RateLimiter(limit=10, window=3600)    # 10 bookings / hour / IP


# --------------------------------------------------------------------------
# Notifications (run in background threads, failures are only logged)
# --------------------------------------------------------------------------
def notify(text):
    threading.Thread(target=_notify, args=(text,), daemon=True).start()


def _notify(text):
    if SMTP_HOST and NOTIFY_EMAIL_TO and SMTP_USER:
        try:
            msg = EmailMessage()
            msg["Subject"] = "New booking / order request - LALA Restaurant"
            msg["From"] = SMTP_FROM
            msg["To"] = NOTIFY_EMAIL_TO
            msg.set_content(text)
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
                s.starttls()
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
        except Exception as exc:
            log.warning("Email notification failed: %s", exc)
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": text}).encode()
            urllib.request.urlopen("https://api.telegram.org/bot%s/sendMessage" % TELEGRAM_BOT_TOKEN, data, timeout=15).read()
        except Exception as exc:
            log.warning("Telegram notification failed: %s", type(exc).__name__)
    if CALLMEBOT_PHONE and CALLMEBOT_APIKEY:
        try:
            qs = urllib.parse.urlencode({"phone": CALLMEBOT_PHONE, "text": text, "apikey": CALLMEBOT_APIKEY})
            urllib.request.urlopen("https://api.callmebot.com/whatsapp.php?" + qs, timeout=15).read()
        except Exception as exc:
            log.warning("WhatsApp notification failed: %s", type(exc).__name__)


# --------------------------------------------------------------------------
# HTTP handler
# --------------------------------------------------------------------------
def clean(value, limit):
    return str(value if value is not None else "").strip()[:limit]


class Handler(SimpleHTTPRequestHandler):
    server_version = "LalaServer"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    # ---- helpers -----------------------------------------------------------
    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        if ALLOWED_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()

    def client_ip(self):
        if TRUST_PROXY:
            fwd = self.headers.get("X-Forwarded-For", "")
            if fwd:
                return fwd.split(",")[-1].strip()
        return self.client_address[0]

    def send_json(self, data, code=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def fail(self, message, code=400):
        self.send_json({"status": "error", "message": message}, code)

    def read_json(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length > MAX_BODY:
            raise ValueError("Request too large")
        body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        if not isinstance(body, dict):
            raise ValueError("Invalid JSON body")
        return body

    def require_admin(self):
        header = self.headers.get("Authorization", "")
        if header.startswith("Bearer ") and valid_token(header[7:]):
            return True
        self.fail("Unauthorized", 401)
        return False

    @staticmethod
    def static_allowed(path):
        if path == "/":
            return True
        if any(part.startswith(".") for part in path.split("/")):
            return False
        return os.path.splitext(path)[1].lower() in STATIC_EXT

    def list_directory(self, path):
        self.send_error(404)
        return None

    # ---- routing -----------------------------------------------------------
    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_HEAD(self):
        if not self.static_allowed(urllib.parse.urlsplit(self.path).path):
            return self.send_error(404)
        return super().do_HEAD()

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        try:
            if path == "/health":
                return self.send_json({"status": "ok"})
            if path == "/api/settings":
                with closing(db()) as conn:
                    rows = conn.execute("SELECT key, value FROM settings").fetchall()
                return self.send_json({"status": "success", "data": {r["key"]: r["value"] for r in rows}})
            if path == "/api/menu_items":
                with closing(db()) as conn:
                    rows = conn.execute("SELECT * FROM menu_items WHERE is_active = 1 ORDER BY id ASC").fetchall()
                return self.send_json({"status": "success", "data": [dict(r) for r in rows]})
            if path == "/api/reservations":
                if not self.require_admin():
                    return
                with closing(db()) as conn:
                    rows = conn.execute("SELECT * FROM reservations ORDER BY id DESC").fetchall()
                return self.send_json({"status": "success", "data": [dict(r) for r in rows]})
            if path == "/api/export/reservations.csv":
                if not self.require_admin():
                    return
                return self.export_csv()
            if path.startswith("/api/"):
                return self.fail("Endpoint not found", 404)
        except Exception:
            log.exception("GET %s failed", path)
            return self.fail("Server error", 500)

        if not self.static_allowed(path):
            return self.send_error(404)
        return super().do_GET()

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        try:
            body = self.read_json()
        except (ValueError, json.JSONDecodeError):
            return self.fail("Invalid request body")
        try:
            if path == "/api/login":
                return self.login(body)
            if path == "/api/reservations":
                return self.create_reservation(body)
            if not self.require_admin():
                return
            if path == "/api/reservations/update_status":
                return self.update_status(body)
            if path == "/api/settings":
                return self.save_settings(body)
            if path == "/api/menu_items":
                return self.save_menu_item(body)
            if path == "/api/menu_items/delete":
                return self.delete_menu_item(body)
            return self.fail("Endpoint not found", 404)
        except Exception:
            log.exception("POST %s failed", path)
            return self.fail("Server error", 500)

    # ---- endpoints ---------------------------------------------------------
    def login(self, body):
        ip = self.client_ip()
        if login_fails.blocked(ip):
            return self.fail("Too many attempts. Try again in a few minutes.", 429)
        supplied = clean(body.get("password"), 200).encode()
        if hmac.compare_digest(supplied, ADMIN_PASSWORD.encode()):
            return self.send_json({"status": "success", "token": make_token()})
        login_fails.add(ip)
        return self.fail("Wrong password", 401)

    def create_reservation(self, body):
        ip = self.client_ip()
        if booking_limit.blocked(ip):
            return self.fail("Too many requests. Please call us directly.", 429)
        name = clean(body.get("name"), 80)
        phone = clean(body.get("phone"), 20)
        if not name or not re.fullmatch(r"\+?[0-9][0-9 \-]{5,17}[0-9]", phone):
            return self.fail("Please enter your name and a valid phone number.")
        booking_limit.add(ip)
        values = (
            name, phone,
            clean(body.get("request_type"), 40) or "Table Reservation",
            clean(body.get("guest_count"), 40),
            clean(body.get("preferred_date"), 20),
            clean(body.get("preferred_time"), 40),
            clean(body.get("special_notes"), 500),
        )
        with closing(db()) as conn, conn:
            cur = conn.execute(
                "INSERT INTO reservations (name, phone, request_type, guest_count, preferred_date, preferred_time, special_notes) VALUES (?,?,?,?,?,?,?)",
                values)
            new_id = cur.lastrowid
        notify("New request #%d\nType: %s\nName: %s\nPhone: %s\nGuests: %s\nDate: %s %s\nNotes: %s" % (
            new_id, values[2], values[0], values[1], values[3] or "-", values[4] or "-", values[5], values[6] or "-"))
        return self.send_json({"status": "success", "id": new_id, "message": "Reservation saved!"}, 201)

    def update_status(self, body):
        status = body.get("status")
        try:
            rid = int(body.get("id"))
        except (TypeError, ValueError):
            return self.fail("Invalid id")
        if status not in STATUSES:
            return self.fail("Invalid status")
        with closing(db()) as conn, conn:
            conn.execute("UPDATE reservations SET status = ? WHERE id = ?", (status, rid))
        return self.send_json({"status": "success", "message": "Status updated!"})

    def save_settings(self, body):
        with closing(db()) as conn, conn:
            for key, val in body.items():
                if key in DEFAULT_SETTINGS:  # ignore unknown keys
                    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, clean(val, 500)))
        return self.send_json({"status": "success", "message": "Settings updated successfully!"})

    def save_menu_item(self, body):
        name = clean(body.get("name"), 100)
        price = clean(body.get("price"), 10)
        if not name or not re.fullmatch(r"\d{1,6}(\.\d{1,2})?", price):
            return self.fail("Item name and a numeric price are required.")
        image_url = clean(body.get("image_url"), 500) or DEFAULT_MENU[0][5]
        if not image_url.startswith(("https://", "http://", "/")):
            return self.fail("Image link must start with https://")
        fields = (name, clean(body.get("category"), 30) or "biryani", price,
                  clean(body.get("description"), 400), clean(body.get("badge"), 40), image_url)
        item_id = body.get("id")
        with closing(db()) as conn, conn:
            if item_id:
                try:
                    item_id = int(item_id)
                except (TypeError, ValueError):
                    return self.fail("Invalid id")
                conn.execute("UPDATE menu_items SET name=?, category=?, price=?, description=?, badge=?, image_url=? WHERE id=?",
                             fields + (item_id,))
            else:
                conn.execute("INSERT INTO menu_items (name, category, price, description, badge, image_url, is_active) VALUES (?,?,?,?,?,?,1)", fields)
        return self.send_json({"status": "success", "message": "Menu item saved!"})

    def delete_menu_item(self, body):
        try:
            item_id = int(body.get("id"))
        except (TypeError, ValueError):
            return self.fail("Invalid id")
        with closing(db()) as conn, conn:
            conn.execute("UPDATE menu_items SET is_active = 0 WHERE id = ?", (item_id,))
        return self.send_json({"status": "success", "message": "Menu item deleted!"})

    def export_csv(self):
        with closing(db()) as conn:
            rows = conn.execute("SELECT id, name, phone, request_type, guest_count, preferred_date, preferred_time, special_notes, status, created_at FROM reservations ORDER BY id DESC").fetchall()
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["ID", "Name", "Phone", "Type", "Guests", "Date", "Time", "Notes", "Status", "Created"])
        for r in rows:
            safe = [("'" + str(v)) if str(v).startswith(("=", "+", "-", "@")) and i in (1, 7) else v
                    for i, v in enumerate(tuple(r))]
            writer.writerow(safe)
        data = out.getvalue().encode("utf-8-sig")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="reservations.csv"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run():
    init_db()
    threading.Thread(target=backup_loop, daemon=True).start()
    channels = [n for n, on in (("email", SMTP_HOST and NOTIFY_EMAIL_TO), ("telegram", TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
                                ("whatsapp", CALLMEBOT_PHONE and CALLMEBOT_APIKEY)) if on]
    log.info("Notifications: %s", ", ".join(channels) or "none configured")
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    log.info("Server running on http://%s:%d  (admin: /admin.html)", HOST, PORT)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down")


if __name__ == "__main__":
    run()
