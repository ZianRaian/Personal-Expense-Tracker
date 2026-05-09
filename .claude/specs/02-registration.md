# Spec: Registration

## Overview
Implement user registration so new visitors can create a Spendly account. This step wires up the existing `POST /register` stub into a fully working form handler: it validates input, checks for duplicate emails, hashes the password with werkzeug, inserts the user into the database, and redirects to the login page on success. Flask sessions and flash messaging are introduced here and will be used by all future authenticated steps.

## Depends on
- Step 01 — Database Setup (users table must exist)

## Routes
- `GET /register` — render registration form — public (already exists, no change needed)
- `POST /register` — process registration form — public

## Database changes
No new tables or columns. The `users` table from Step 01 already has all required columns (`id`, `name`, `email`, `password_hash`, `created_at`).

Add two helper functions to `database/db.py`:
- `get_user_by_email(email)` — returns a user row or `None`
- `create_user(name, email, password_hash)` — inserts a new user and returns the new `id`

## Templates
- **Modify:** `templates/register.html`
  - Add `<form method="POST" action="/register">`
  - Add fields: `name`, `email`, `password`, `confirm_password`
  - Display flashed error/success messages
  - All inputs must have `name` attributes matching what the route reads
  - Template must extend `base.html`

## Files to change
- `app.py` — set `app.secret_key`, add imports (`request`, `redirect`, `url_for`, `flash`, `session`), implement `POST /register` handler
- `database/db.py` — add `get_user_by_email()` and `create_user()` functions
- `templates/register.html` — wire up form, add flash message display

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — no string interpolation in SQL
- Passwords hashed with `werkzeug.security.generate_password_hash`
- Use CSS variables — never hardcode hex values in templates or static files
- All templates extend `base.html`
- `app.secret_key` must be set before any session or flash usage; use a hardcoded dev string for now (e.g. `"spendly-dev-secret"`)
- Validate all fields server-side: name required, valid email format, password minimum 6 chars, passwords must match
- If email already exists show a field-level flash error and re-render the form — do not redirect
- On success: flash a success message and `redirect(url_for('login'))`
- Do not log the user in automatically after registration — login is Step 3

## Definition of done
- [ ] Visiting `/register` shows a form with name, email, password, and confirm password fields
- [ ] Submitting the form with valid data creates a new user row in the database with a hashed password
- [ ] Submitting with a duplicate email re-renders the form with an error message, no new row inserted
- [ ] Submitting with mismatched passwords re-renders the form with an error message
- [ ] Submitting with any empty field re-renders the form with an error message
- [ ] Successful registration redirects to `/login`
- [ ] Registered user can be verified in the database with a hashed (not plain-text) password
- [ ] App starts without errors
