# Spec: Backend Routes for Profile Page

## Overview
This step replaces the hardcoded dummy data in the `/profile` route with live queries
against the SQLite database. The profile page already exists with a polished design
(Step 04); this step wires it up to real user data. The route will fetch the logged-in
user's record, compute aggregate stats (total spent, transaction count, top category),
retrieve their five most recent expenses, and calculate per-category spending totals with
percentages. All data work is done in `database/db.py` as helper functions; `app.py`
calls those functions and passes results to the template unchanged.

## Depends on
- Step 01: Database setup (users + expenses tables must exist)
- Step 03: Login / logout (session must carry `user_id`)
- Step 04: Profile page template must already exist

## Routes
- `GET /profile` — already exists; modify to query DB instead of returning hardcoded data — logged-in only

No new routes.

## Database changes
No schema changes. New query functions added to `database/db.py`:

- `get_user_by_id(user_id)` — fetch a single user row by primary key
- `get_expense_stats(user_id)` — return dict with `total_spent` (REAL), `transaction_count` (int), `top_category` (str or None)
- `get_recent_expenses(user_id, limit=5)` — return list of expense rows ordered by date DESC
- `get_category_totals(user_id)` — return list of dicts `{name, amount, pct}` sorted by amount DESC; `pct` is integer 0-100

## Templates
- **Modify:** `templates/profile.html` — no structural changes; ensure template handles the case where a user has zero expenses gracefully (empty state for transactions table and category breakdown)

## Files to change
- `database/db.py` — add four new query functions (listed above)
- `app.py` — rewrite the `/profile` route body to call the new DB functions; format amounts as `৳{value:,.0f}` strings; derive `member_since` from `user["created_at"]`; keep the same variable names passed to the template (`user`, `stats`, `transactions`, `categories`)

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never string-format SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Amount formatting: use Python f-string `f"৳{amount:,.0f}"` — comma thousands separator, zero decimal places
- `member_since` must be derived from `users.created_at` (stored as `datetime('now')` ISO string); format as "Month YYYY" (e.g. "May 2026")
- `top_category` query must use `GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1`; return `"—"` if user has no expenses
- `pct` in category totals: `round(category_total / grand_total * 100)` as int; grand total is sum of all user's expenses
- `get_recent_expenses` returns raw sqlite3.Row objects; the template accesses `row["date"]`, `row["description"]`, `row["category"]`, `row["amount"]`
- Profile route must still redirect to `/login` if `session["user_id"]` is absent
- Do not break any existing routes

## Definition of done
- [ ] Visiting `/profile` while logged in returns HTTP 200 with no Python errors
- [ ] User name, email, and member-since date shown on profile are pulled from the `users` table (not hardcoded)
- [ ] "Total Spent" stat reflects the actual sum of that user's expenses in the DB
- [ ] "Transactions" stat reflects the actual count of that user's expenses
- [ ] "Top Category" stat shows the category with the highest total spend; shows "—" when user has no expenses
- [ ] Recent transactions table shows up to 5 real rows from the `expenses` table, newest first
- [ ] Category breakdown shows real per-category totals and percentages
- [ ] A freshly seeded demo user (via `/seed-user`) shows their own data, not the demo user's data
- [ ] A user with zero expenses sees an empty transactions table and an empty category breakdown without a Python error
- [ ] Logging out and logging back in as a different user shows that user's data
