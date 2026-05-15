# Spec: Add Expense

## Overview
Implement the Add Expense feature so logged-in users can record a new spending entry via
a form at `/expenses/add`. The user fills in amount, category (from a fixed list), date,
and an optional description; submitting the form inserts one row into the `expenses` table
and redirects to the profile page with a success flash message. This is the first write
operation in Spendly and the gateway to all future expense management steps (edit, delete).

## Depends on
- Step 01 — Database Setup (`expenses` table must exist with all required columns)
- Step 03 — Login / Logout (session must carry `user_id`)
- Step 05 — Backend Routes for Profile Page (profile page is the redirect target)

## Routes
- `GET /expenses/add` — Display the add-expense form — logged-in only
- `POST /expenses/add` — Validate and save the new expense, redirect to `/profile` — logged-in only

## Database changes
No schema changes. The `expenses` table already has all required columns:
`id`, `user_id`, `amount`, `category`, `date`, `description`, `created_at`.

Add one new function to `database/db.py`:

```python
def add_expense(user_id, amount, category, date, description):
    # Inserts one row; returns the new expense id
```

## Templates
- **Create:** `templates/add_expense.html`
  - Extends `base.html`
  - Form with `method="POST"` and `action="{{ url_for('add_expense') }}"`
  - Fields:
    - Amount (number input, step="0.01", min="0.01", required)
    - Category (`<select>` with fixed options: Food, Transport, Bills, Health, Entertainment, Shopping, Other; required)
    - Date (date input, required, defaults to today via `value="{{ today }}"`)
    - Description (textarea, optional, max 200 chars)
  - Submit button: "Add Expense"
  - Error message area rendered when `error` context variable is set
  - Link back to profile: "← Back to Profile"
- **Modify:** `templates/profile.html`
  - Add an "Add Expense" button/link (using `url_for('add_expense')`) near the transactions section header

## Files to change
- `database/db.py`
  - Add `add_expense(user_id, amount, category, date, description)` function
- `app.py`
  - Import `add_expense` from `database.db`
  - Convert the existing stub `GET /expenses/add` route into a full `GET`/`POST` handler with auth guard, validation, DB insert, and redirect
  - Pass `today` (today's date as ISO string) to the template on GET
- `templates/profile.html`
  - Add "Add Expense" button linking to `/expenses/add`
- `static/css/style.css`
  - Add styles for the add-expense form page (`.add-expense-form`, field layout, submit button)

## Files to create
- `templates/add_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never string-format SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Auth guard: redirect unauthenticated users to `/login`
- Amount validation: must convert to a positive float > 0; reject non-numeric or zero/negative values
- Category validation: must be one of the fixed list — reject any value not in the list
- Date validation: must match `YYYY-MM-DD` and be a real calendar date; use `date.fromisoformat()`
- Description: optional; strip whitespace; store `None` (not empty string) when blank — consistent with seed data
- On validation failure: re-render the form with the error message and previously entered values so the user does not lose their input
- On success: `flash("Expense added.", "success")` then `redirect(url_for("profile"))`
- The fixed category list must be defined once in `app.py` and passed to the template as `categories` — do not hardcode it in two places

## Definition of done
- [ ] `GET /expenses/add` while logged out redirects to `/login`
- [ ] `GET /expenses/add` while logged in renders the form with today's date pre-filled
- [ ] Submitting the form with all valid fields saves the expense and redirects to `/profile` with a success flash
- [ ] The new expense appears in the profile page's recent transactions list
- [ ] Total Spent and Transaction Count on the profile page increase correctly after adding an expense
- [ ] Submitting with a blank amount shows a validation error and re-renders the form
- [ ] Submitting with a non-numeric amount shows a validation error
- [ ] Submitting with a zero or negative amount shows a validation error
- [ ] Submitting with an invalid category (not in the fixed list) shows a validation error
- [ ] Submitting with a blank date shows a validation error
- [ ] Submitting with an invalid date string (e.g. "2026-13-01") shows a validation error
- [ ] Submitting with a description longer than 200 characters shows a validation error
- [ ] An optional description left blank is stored as `NULL` in the database, not as an empty string
- [ ] The "Add Expense" button on the profile page links correctly to `/expenses/add`
- [ ] App starts without errors
