from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import (get_db, init_db, seed_db, get_user_by_email, create_user,
                          get_user_by_id, get_expense_stats,
                          get_recent_expenses, get_category_totals)

app = Flask(__name__)
app.secret_key = "spendly-dev-secret"

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    if request.method == "GET":
        return render_template("register.html")

    name             = request.form.get("name", "").strip()
    email            = request.form.get("email", "").strip().lower()
    password         = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not name or not email or not password or not confirm_password:
        return render_template("register.html", error="All fields are required.")
    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters.")
    if password != confirm_password:
        return render_template("register.html", error="Passwords do not match.")
    if get_user_by_email(email):
        return render_template("register.html", error="An account with that email already exists.")

    create_user(name, email, generate_password_hash(password))
    flash("Account created! Please sign in.", "success")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email    = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template("login.html", error="Email and password are required.")

    user = get_user_by_email(email)
    if not user or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.")

    session["user_id"]   = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]

    # ── SECTION A: USER ─────────────────────────────────────────────── #
    db_user = get_user_by_id(user_id)
    _month_names = ["January","February","March","April","May","June",
                    "July","August","September","October","November","December"]
    _y, _m = db_user["created_at"][:7].split("-")
    initials = "".join(w[0].upper() for w in db_user["name"].split()[:2])
    user = {
        "name":         db_user["name"],
        "email":        db_user["email"],
        "initials":     initials,
        "member_since": f"{_month_names[int(_m)-1]} {_y}",
    }

    # ── SECTION B: STATS ────────────────────────────────────────────── #
    raw_stats = get_expense_stats(user_id)
    stats = {
        "total_spent":       f"৳{raw_stats['total_spent']:,.0f}",
        "transaction_count": raw_stats["transaction_count"],
        "top_category":      raw_stats["top_category"] or "—",
    }

    # ── SECTION C: TRANSACTIONS ─────────────────────────────────────── #
    _months = ["Jan","Feb","Mar","Apr","May","Jun",
               "Jul","Aug","Sep","Oct","Nov","Dec"]
    def _fmt_date(iso):
        y, m, d = iso.split("-")
        return f"{_months[int(m)-1]} {int(d)}, {y}"
    transactions = [
        {
            "date":        _fmt_date(row["date"]),
            "description": row["description"] or "",
            "category":    row["category"],
            "amount":      f"৳{row['amount']:,.0f}",
        }
        for row in get_recent_expenses(user_id)
    ]

    # ── SECTION D: CATEGORIES ───────────────────────────────────────── #
    categories = [
        {
            "name":   cat["name"],
            "amount": f"৳{cat['amount']:,.0f}",
            "pct":    cat["pct"],
        }
        for cat in get_category_totals(user_id)
    ]

    return render_template("profile.html",
        user=user, stats=stats,
        transactions=transactions, categories=categories)


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
