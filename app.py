from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db, get_user_by_email, create_user

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

    initials = "".join(w[0].upper() for w in session.get("user_name", "U").split()[:2])

    user = {
        "name":         session.get("user_name", "User"),
        "email":        "demo@spendly.com",
        "initials":     initials,
        "member_since": "January 2025",
    }

    stats = {
        "total_spent":       "৳18,450",
        "transaction_count": 24,
        "top_category":      "Food",
    }

    transactions = [
        {"date": "May 10, 2026", "description": "Grocery run",     "category": "Food",      "amount": "৳1,200"},
        {"date": "May 8, 2026",  "description": "Uber ride",        "category": "Transport", "amount": "৳350"},
        {"date": "May 5, 2026",  "description": "Electricity bill", "category": "Bills",     "amount": "৳2,800"},
        {"date": "May 3, 2026",  "description": "Dinner out",       "category": "Food",      "amount": "৳950"},
        {"date": "Apr 28, 2026", "description": "Pharmacy",         "category": "Health",    "amount": "৳600"},
    ]

    categories = [
        {"name": "Food",      "amount": "৳6,200", "pct": 34},
        {"name": "Bills",     "amount": "৳5,100", "pct": 28},
        {"name": "Transport", "amount": "৳3,400", "pct": 18},
        {"name": "Health",    "amount": "৳2,100", "pct": 11},
        {"name": "Other",     "amount": "৳1,650", "pct":  9},
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
