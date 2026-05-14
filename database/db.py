import sqlite3
import os
from datetime import date, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "spendly.db")


def _period_dates(period):
    today = date.today()
    if period == "this_month":
        return today.replace(day=1).isoformat(), today.isoformat()
    if period == "last_3_months":
        return (today - timedelta(days=90)).isoformat(), today.isoformat()
    if period == "last_6_months":
        return (today - timedelta(days=180)).isoformat(), today.isoformat()
    return None, None


def _date_clause(date_from, date_to):
    if date_from and date_to:
        return " AND date BETWEEN ? AND ?", [date_from, date_to]
    return "", []


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            amount      REAL    NOT NULL,
            category    TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            description TEXT,
            created_at  TEXT    DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


def seed_db():
    conn = get_db()
    if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        conn.close()
        return
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
    )
    user_id = cur.lastrowid
    expenses = [
        (user_id, 450.00,  "Food",          "2026-05-01", "Groceries"),
        (user_id, 120.00,  "Transport",     "2026-05-02", "Rickshaw"),
        (user_id, 1500.00, "Bills",         "2026-05-03", "Electricity bill"),
        (user_id, 800.00,  "Health",        "2026-05-05", "Pharmacy"),
        (user_id, 300.00,  "Entertainment", "2026-05-07", "Cinema"),
        (user_id, 950.00,  "Shopping",      "2026-05-09", "Clothes"),
        (user_id, 200.00,  "Other",         "2026-05-10", "Miscellaneous"),
        (user_id, 350.00,  "Food",          "2026-05-12", "Restaurant"),
    ]
    cur.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        expenses,
    )
    conn.commit()
    conn.close()


def get_user_by_email(email):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return user


def create_user(name, email, password_hash):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, password_hash),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id


def get_user_by_id(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user


def get_expense_stats(user_id, date_from=None, date_to=None):
    conn = get_db()
    clause, extra = _date_clause(date_from, date_to)
    params = [user_id] + extra
    row = conn.execute(
        f"SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
        f"FROM expenses WHERE user_id = ?{clause}",
        params
    ).fetchone()
    top = conn.execute(
        f"SELECT category FROM expenses WHERE user_id = ?{clause} "
        "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
        params
    ).fetchone()
    conn.close()
    return {
        "total_spent":       row["total"],
        "transaction_count": row["cnt"],
        "top_category":      top["category"] if top else None,
    }


def get_recent_expenses(user_id, limit=5, date_from=None, date_to=None):
    conn = get_db()
    clause, extra = _date_clause(date_from, date_to)
    params = [user_id] + extra + [limit]
    rows = conn.execute(
        f"SELECT * FROM expenses WHERE user_id = ?{clause} ORDER BY date DESC LIMIT ?",
        params
    ).fetchall()
    conn.close()
    return rows


def get_category_totals(user_id, date_from=None, date_to=None):
    conn = get_db()
    clause, extra = _date_clause(date_from, date_to)
    params = [user_id] + extra
    grand = conn.execute(
        f"SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?{clause}",
        params
    ).fetchone()[0]
    rows = conn.execute(
        f"SELECT category, SUM(amount) AS total FROM expenses "
        f"WHERE user_id = ?{clause} GROUP BY category ORDER BY total DESC",
        params
    ).fetchall()
    conn.close()
    if not grand:
        return []
    return [
        {
            "name":   row["category"],
            "amount": row["total"],
            "pct":    round(row["total"] / grand * 100),
        }
        for row in rows
    ]
