# Spec: Login and Logout

## Overview
Implement session-based login and logout so registered users can authenticate into Spendly and securely end their session. The `POST /login` route verifies credentials against the database using `check_password_hash`, stores user identity in Flask's server-side session, and redirects to `/profile`. The `GET /logout` route clears the session and redirects to `/login`. This step introduces the session layer that all future authenticated routes will depend on.

## Depends on
- Step 01 — Database Setup (users table must exist)
- Step 02 — Registration (users must exist in the database to log in)

## Routes
- `GET /login` — render login form — public (already exists as stub, add `POST` method)
- `POST /login` — validate credentials, set session, redirect — public
- `GET /logout` — clear session, redirect to `/login` — public (no auth guard needed yet)

## Database changes
No new tables or columns. `get_user_by_email(email)` already exists in `database/db.py` and is sufficient.

## Templates
- **Modify:** `templates/login.html`
  - Already has `<form method="POST" action="/login">` with `email` and `password` fields
  - Already renders `{{ error }}` — no change needed to template structure
  - No modification required if the route passes `error=` consistently

## Files to change
- `app.py`
  - Add `session` to flask imports
  - Add `check_password_hash` to werkzeug.security imports
  - Change `@app.route("/login")` to `@app.route("/login", methods=["GET", "POST"])`
  - Implement `POST /login` handler
  - Implement `GET /logout` handler (replace stub)

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — no string interpolation in SQL
- Passwords verified with `werkzeug.security.check_password_hash` — never compare plain text
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Session must store `session['user_id']` (int) and `session['user_name']` (str) on successful login
- On bad credentials: re-render `login.html` with `error="Invalid email or password."` — do not reveal which field is wrong
- On success: `redirect(url_for('profile'))`
- Logout: call `session.clear()`, then `redirect(url_for('login'))`
- Do not add a `@login_required` decorator in this step — auth guards come in a later step

## Definition of done
- [ ] `GET /login` renders the login form
- [ ] `POST /login` with correct email and password sets `session['user_id']` and `session['user_name']` and redirects to `/profile`
- [ ] `POST /login` with wrong password re-renders the form with `"Invalid email or password."` error, no session set
- [ ] `POST /login` with unknown email re-renders the form with the same generic error
- [ ] `POST /login` with empty fields re-renders the form with a validation error
- [ ] `GET /logout` clears the session and redirects to `/login`
- [ ] After logout, `session['user_id']` is no longer present
- [ ] Demo user (`demo@spendly.com` / `demo123`) can log in successfully
- [ ] App starts without errors
