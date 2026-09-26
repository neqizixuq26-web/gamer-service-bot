import sqlite3
import os
import time

DB_PATH = os.environ.get("DB_PATH", "bot.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0,
            total_deposit REAL DEFAULT 0,
            total_spent REAL DEFAULT 0,
            total_withdraw REAL DEFAULT 0,
            referral_earnings REAL DEFAULT 0,
            referred_by INTEGER,
            joined_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS buy_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            price REAL,
            min_qty INTEGER,
            max_qty INTEGER,
            instruction TEXT,
            status INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS sell_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            price REAL,
            min_qty INTEGER,
            instruction TEXT,
            status INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            service_id INTEGER,
            service_name TEXT,
            qty INTEGER,
            amount REAL,
            details TEXT,
            status TEXT DEFAULT 'Pending',
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS sell_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            service_id INTEGER,
            service_name TEXT,
            qty INTEGER,
            details TEXT,
            status TEXT DEFAULT 'Pending',
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            method TEXT,
            amount REAL,
            txn_id TEXT,
            status TEXT DEFAULT 'Pending',
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            method TEXT,
            account TEXT,
            amount REAL,
            status TEXT DEFAULT 'Pending',
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER,
            bonus_paid INTEGER DEFAULT 0,
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    defaults = {
        "min_deposit": "50",
        "referral_bonus": "2",
        "channel_username": os.environ.get("CHANNEL_USERNAME", "@yourchannel"),
        "channel_link": os.environ.get("CHANNEL_LINK", "https://t.me/yourchannel"),
        "support_link": os.environ.get("SUPPORT_LINK", "https://t.me/yoursupport"),
        "details_text": "এখানে Bot ব্যবহারের নিয়ম, Payment Information ও গুরুত্বপূর্ণ নির্দেশনা থাকবে।\n\nAdmin Panel থেকে এই লেখা পরিবর্তন করা যাবে।",
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()


# ---------- settings ----------
def get_setting(key, default=None):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_conn()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
    conn.commit()
    conn.close()


# ---------- users ----------
def get_user(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row


def get_or_create_user(user_id, username, referred_by=None):
    user = get_user(user_id)
    if user:
        return user
    conn = get_conn()
    conn.execute(
        "INSERT INTO users (user_id, username, referred_by, joined_at) VALUES (?, ?, ?, ?)",
        (user_id, username, referred_by, int(time.time())),
    )
    conn.commit()
    conn.close()
    if referred_by:
        conn = get_conn()
        conn.execute(
            "INSERT INTO referrals (referrer_id, referred_id, created_at) VALUES (?, ?, ?)",
            (referred_by, user_id, int(time.time())),
        )
        conn.commit()
        conn.close()
    return get_user(user_id)


def update_balance(user_id, delta, extra_field=None):
    """delta can be negative. extra_field is one of total_deposit/total_spent/total_withdraw/referral_earnings
    which also gets incremented by abs(delta)."""
    conn = get_conn()
    conn.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (delta, user_id))
    if extra_field:
        conn.execute(
            f"UPDATE users SET {extra_field} = {extra_field} + ? WHERE user_id=?",
            (abs(delta), user_id),
        )
    conn.commit()
    conn.close()


def get_referral_stats(user_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM referrals WHERE referrer_id=?", (user_id,)
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def get_unpaid_referral(referred_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM referrals WHERE referred_id=? AND bonus_paid=0", (referred_id,)
    ).fetchone()
    conn.close()
    return row


def mark_referral_paid(ref_row_id):
    conn = get_conn()
    conn.execute("UPDATE referrals SET bonus_paid=1 WHERE id=?", (ref_row_id,))
    conn.commit()
    conn.close()


# ---------- buy services ----------
def add_buy_service(name, description, price, min_qty, max_qty, instruction):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO buy_services (name, description, price, min_qty, max_qty, instruction) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (name, description, price, min_qty, max_qty, instruction),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


def get_buy_services(active_only=False):
    conn = get_conn()
    q = "SELECT * FROM buy_services"
    if active_only:
        q += " WHERE status=1"
    rows = conn.execute(q + " ORDER BY id DESC").fetchall()
    conn.close()
    return rows


def get_buy_service(sid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM buy_services WHERE id=?", (sid,)).fetchone()
    conn.close()
    return row


def update_buy_service_field(sid, field, value):
    conn = get_conn()
    conn.execute(f"UPDATE buy_services SET {field}=? WHERE id=?", (value, sid))
    conn.commit()
    conn.close()


def toggle_buy_service(sid):
    conn = get_conn()
    conn.execute("UPDATE buy_services SET status = 1 - status WHERE id=?", (sid,))
    conn.commit()
    conn.close()


def delete_buy_service(sid):
    conn = get_conn()
    conn.execute("DELETE FROM buy_services WHERE id=?", (sid,))
    conn.commit()
    conn.close()


# ---------- sell services ----------
def add_sell_service(name, description, price, min_qty, instruction):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO sell_services (name, description, price, min_qty, instruction) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, description, price, min_qty, instruction),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


def get_sell_services(active_only=False):
    conn = get_conn()
    q = "SELECT * FROM sell_services"
    if active_only:
        q += " WHERE status=1"
    rows = conn.execute(q + " ORDER BY id DESC").fetchall()
    conn.close()
    return rows


def get_sell_service(sid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM sell_services WHERE id=?", (sid,)).fetchone()
    conn.close()
    return row


def update_sell_service_field(sid, field, value):
    conn = get_conn()
    conn.execute(f"UPDATE sell_services SET {field}=? WHERE id=?", (value, sid))
    conn.commit()
    conn.close()


def toggle_sell_service(sid):
    conn = get_conn()
    conn.execute("UPDATE sell_services SET status = 1 - status WHERE id=?", (sid,))
    conn.commit()
    conn.close()


def delete_sell_service(sid):
    conn = get_conn()
    conn.execute("DELETE FROM sell_services WHERE id=?", (sid,))
    conn.commit()
    conn.close()


# ---------- orders (buy) ----------
def create_order(user_id, service_id, service_name, qty, amount, details):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO orders (user_id, service_id, service_name, qty, amount, details, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, service_id, service_name, qty, amount, details, int(time.time())),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


def get_order(oid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    conn.close()
    return row


def update_order_status(oid, status):
    conn = get_conn()
    conn.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
    conn.commit()
    conn.close()


def get_user_orders(user_id, limit=15):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)
    ).fetchall()
    conn.close()
    return rows


def get_orders_by_status(status="Pending", limit=20):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM orders WHERE status=? ORDER BY id DESC LIMIT ?", (status, limit)
    ).fetchall()
    conn.close()
    return rows


# ---------- sell requests ----------
def create_sell_request(user_id, service_id, service_name, qty, details):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO sell_requests (user_id, service_id, service_name, qty, details, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, service_id, service_name, qty, details, int(time.time())),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


def get_sell_request(sid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM sell_requests WHERE id=?", (sid,)).fetchone()
    conn.close()
    return row


def update_sell_request_status(sid, status):
    conn = get_conn()
    conn.execute("UPDATE sell_requests SET status=? WHERE id=?", (status, sid))
    conn.commit()
    conn.close()


def get_user_sell_requests(user_id, limit=15):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM sell_requests WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return rows


def get_sell_requests_by_status(status="Pending", limit=20):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM sell_requests WHERE status=? ORDER BY id DESC LIMIT ?",
        (status, limit),
    ).fetchall()
    conn.close()
    return rows


# ---------- deposits ----------
def create_deposit(user_id, method, amount, txn_id):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO deposits (user_id, method, amount, txn_id, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, method, amount, txn_id, int(time.time())),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


def get_deposit(did):
    conn = get_conn()
    row = conn.execute("SELECT * FROM deposits WHERE id=?", (did,)).fetchone()
    conn.close()
    return row


def update_deposit_status(did, status):
    conn = get_conn()
    conn.execute("UPDATE deposits SET status=? WHERE id=?", (status, did))
    conn.commit()
    conn.close()


def get_user_deposits(user_id, limit=15):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM deposits WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)
    ).fetchall()
    conn.close()
    return rows


def get_pending_deposits(limit=20):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM deposits WHERE status='Pending' ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return rows


# ---------- withdrawals ----------
def create_withdrawal(user_id, method, account, amount):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO withdrawals (user_id, method, account, amount, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, method, account, amount, int(time.time())),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


def get_withdrawal(wid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM withdrawals WHERE id=?", (wid,)).fetchone()
    conn.close()
    return row


def update_withdrawal_status(wid, status):
    conn = get_conn()
    conn.execute("UPDATE withdrawals SET status=? WHERE id=?", (status, wid))
    conn.commit()
    conn.close()


def get_user_withdrawals(user_id, limit=15):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM withdrawals WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)
    ).fetchall()
    conn.close()
    return rows


def get_pending_withdrawals(limit=20):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM withdrawals WHERE status='Pending' ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return rows


# ---------- stats ----------
def get_stats():
    conn = get_conn()
    stats = {}
    stats["users"] = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    stats["buy_services"] = conn.execute("SELECT COUNT(*) c FROM buy_services").fetchone()["c"]
    stats["sell_services"] = conn.execute("SELECT COUNT(*) c FROM sell_services").fetchone()["c"]
    stats["orders"] = conn.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]
    stats["sell_requests"] = conn.execute("SELECT COUNT(*) c FROM sell_requests").fetchone()["c"]
    stats["pending_deposits"] = conn.execute(
        "SELECT COUNT(*) c FROM deposits WHERE status='Pending'"
    ).fetchone()["c"]
    stats["pending_withdrawals"] = conn.execute(
        "SELECT COUNT(*) c FROM withdrawals WHERE status='Pending'"
    ).fetchone()["c"]
    total_deposit = conn.execute("SELECT SUM(total_deposit) s FROM users").fetchone()["s"]
    stats["total_deposit"] = total_deposit or 0
    conn.close()
    return stats
