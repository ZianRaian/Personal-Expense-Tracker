# Spec: Date Filter for Profile Page

## Overview
Add a date-range filter to the profile page so users can scope all displayed data —
stats, recent transactions, and category breakdown — to a chosen time window. The filter
is a GET query-string parameter (`?period=`) rendered as a tab/button group in the page
header. Four presets are supported: This Month, Last 3 Months, Last 6 Months, and All
Time (default). Selecting a preset reloads the page with the new `?period=` value; the
active preset is visually highlighted. All four database helper functions are updated to
accept optional `date_from` and `date_to` strings (YYYY-MM-DD) so filtered queries work
without duplicating SQL.

## Depends on
- Step 01 — Database Setup (expenses table must exist with `date` column)
- Step 03 — Login / Logout (session must carry `user_id`)
- Step 05 — Backend Routes for Profile Page (live DB queries must already be in place)

## Routes
- `GET /profile?period=<preset>` — existing route; extend to accept `period` query param — logged-in only

No new routes.

## Database changes
No schema changes. The four existing query functions in `database/db.py` gain two optional
keyword parameters:

- `get_expense_stats(user_id, date_from=None, date_to=None)`
- `get_recent_expenses(user_id, limit=5, date_from=None, date_to=None)`
- `get_category_totals(user_id, date_from=None, date_to=None)`

When `date_from` / `date_to` are `None` the queries behave exactly as before (all-time).
When provided, a `AND date BETWEEN ? AND ?` clause is appended.

A small helper `_period_dates(period)` (private, not imported into `app.py`) maps preset
strings to `(date_from, date_to)` tuples using Python's `datetime` module:

| period | date_from | date_to |
|---|---|---|
| `this_month` | first day of current month | today |
| `last_3_months` | today − 90 days | today |
| `last_6_months` | today − 180 days | today |
| `all_time` or anything else | `None` | `None` |

## Templates
- **Modify:** `templates/profile.html`
  - Add a `.filter-bar` element above the stats section containing four `<a>` links:
    - "This Month" → `?period=this_month`
    - "Last 3 Months" → `?period=last_3_months`
    - "Last 6 Months" → `?period=last_6_months`
    - "All Time" → `/profile` (no query string)
  - Add `.filter-btn--active` class to whichever link matches the current `active_period` template variable
  - No other structural changes to the template

## Files to change
- `database/db.py`
  - Add `_period_dates(period)` helper (private)
  - Update `get_expense_stats`, `get_recent_expenses`, `get_category_totals` signatures and SQL to accept `date_from` / `date_to`
- `app.py`
  - In `/profile` route: read `period = request.args.get("period", "all_time")`
  - Compute `date_from, date_to` inline using the same logic as `_period_dates` (or import it)
  - Pass `date_from` / `date_to` to each of the three DB calls
  - Pass `active_period=period` to `render_template`
- `static/css/style.css`
  - Add `.filter-bar` layout and `.filter-btn` / `.filter-btn--active` styles

## Files to create
No new files.

## New dependencies
No new dependencies. `datetime` is standard library.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never string-format SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `period` values not in the known set must fall through to all-time (no 400 error)
- Date arithmetic must use `datetime.date.today()` — no hardcoded dates
- `date_from` / `date_to` must be ISO strings (`YYYY-MM-DD`) when passed to SQL
- The `BETWEEN` clause is inclusive on both ends: `date BETWEEN date_from AND date_to`
- `get_recent_expenses` with a date filter must still respect the `limit` argument
- Filter links must be plain `<a href>` tags — no JavaScript required
- Active filter button must be visually distinct (use `--color-primary` or a border, not just bold)
- The filter bar must not break the responsive layout at ≤ 600px (wrap allowed)

## Definition of done
- [ ] Visiting `/profile` (no query string) shows all-time data — identical to Step 05 behaviour
- [ ] Visiting `/profile?period=this_month` shows only expenses where `date` falls in the current calendar month
- [ ] Visiting `/profile?period=last_3_months` shows only expenses within the past 90 days
- [ ] Visiting `/profile?period=last_6_months` shows only expenses within the past 180 days
- [ ] The active filter button is visually highlighted; the others are not
- [ ] Stats (Total Spent, Transactions, Top Category) update correctly for the chosen period
- [ ] Recent transactions list shows only expenses within the chosen period
- [ ] Category breakdown shows only categories that have expenses within the chosen period
- [ ] A user with no expenses in the chosen period sees empty states without a Python error
- [ ] An unknown `?period=` value falls back to all-time data without a 500 error
- [ ] App starts without errors
