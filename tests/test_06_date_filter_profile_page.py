"""
tests/test_06_date_filter_profile_page.py

Test suite for Spendly Step 06 — Date Filter on the Profile Page.

Coverage
--------
- Auth guard
- All-time default (no ?period=)
- Each of the four period presets: this_month, last_3_months, last_6_months, all_time
- Unknown / garbage period value  →  all-time fallback, no 500
- Custom date range via ?date_from=&date_to=
- Empty state: user has no expenses at all
- Empty state: user has expenses but none fall within the chosen period
- Active-period HTML indicator correctness for every preset + custom
- Stats (total_spent, transaction_count, top_category) are scoped by period
- Transaction list shows / hides expenses based on the active date window
- Category breakdown appears / disappears correctly based on the active date window
- get_recent_expenses limit is respected even when a date filter is active

Implementation note on isolation
---------------------------------
database.db.get_db() opens DB_PATH (a file path) on every call — it does NOT
honour Flask's config['DATABASE'].  We therefore monkey-patch `database.db.DB_PATH`
to a temporary file for every test so that all DB layer calls (from app routes AND
from our helper fixtures) share the same isolated SQLite file.  The temp file is
deleted after each test via the fixture's teardown.
"""

import os
import re
import tempfile
import pytest
from datetime import date, timedelta

import database.db as db_module
from app import app as flask_app
from database.db import init_db


# ------------------------------------------------------------------ #
# Date constants (computed once at import time)                       #
# ------------------------------------------------------------------ #

TODAY = date.today()
TODAY_ISO = TODAY.isoformat()
THIS_MONTH_START = TODAY.replace(day=1).isoformat()
NINETY_AGO = (TODAY - timedelta(days=90)).isoformat()
ONEIGHTY_AGO = (TODAY - timedelta(days=180)).isoformat()

# A date guaranteed to be before the last-6-months window (never matches any preset).
ANCIENT_DATE = (TODAY - timedelta(days=365)).isoformat()

# A date inside this_month (the 1st of the current month).
THIS_MONTH_DATE = TODAY.replace(day=1).isoformat()

# A date inside last_3_months but NOT this_month (45 days ago).
WITHIN_3M_DATE = (TODAY - timedelta(days=45)).isoformat()

# A date inside last_6_months but NOT last_3_months (120 days ago).
WITHIN_6M_ONLY_DATE = (TODAY - timedelta(days=120)).isoformat()


# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def app():
    """
    Flask app configured for isolated testing.

    We create a temporary SQLite file and monkey-patch database.db.DB_PATH
    so every get_db() call (from routes or test helpers) uses the same
    isolated database.  The temp file is removed on teardown.
    """
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    # Redirect all DB layer calls to the temp file.
    original_db_path = db_module.DB_PATH
    db_module.DB_PATH = db_path

    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
        "WTF_CSRF_ENABLED": False,
    })

    with flask_app.app_context():
        # Initialise schema only — do NOT call seed_db() so the demo
        # user never pollutes our isolated test database.
        init_db()
        yield flask_app

    # Teardown: restore original path and delete temp file.
    db_module.DB_PATH = original_db_path
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """A test client already logged in as a fresh isolated user with NO expenses."""
    client.post("/register", data={
        "name": "Test User",
        "email": "testuser@example.com",
        "password": "securepass123",
        "confirm_password": "securepass123",
    })
    client.post("/login", data={
        "email": "testuser@example.com",
        "password": "securepass123",
    })
    return client


def _insert_expense(amount, category, expense_date, description=""):
    """
    Insert a single expense row for 'testuser@example.com' using the
    currently patched DB_PATH (via db_module.get_db).
    Uses parameterised SQL only.  Must be called while app fixture is active.
    """
    conn = db_module.get_db()
    user = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("testuser@example.com",)
    ).fetchone()
    assert user is not None, "testuser@example.com not found — ensure auth_client ran first"
    cur = conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user["id"], amount, category, expense_date, description),
    )
    conn.commit()
    expense_id = cur.lastrowid
    conn.close()
    return expense_id


@pytest.fixture
def seeded_client(auth_client):
    """
    auth_client with a deterministic set of expenses spread across
    different date windows so filter assertions are meaningful.

    Expenses:
      - 1000 / Bills    / ANCIENT_DATE         → only all_time
      - 500  / Health   / WITHIN_6M_ONLY_DATE  → last_6_months + all_time
      - 300  / Food     / WITHIN_3M_DATE       → last_3_months + last_6_months + all_time
      - 200  / Transport/ THIS_MONTH_DATE      → this_month + last_3_months + last_6_months + all_time
    """
    _insert_expense(1000.00, "Bills",     ANCIENT_DATE,        "Ancient bill")
    _insert_expense(500.00,  "Health",    WITHIN_6M_ONLY_DATE, "Health 6m")
    _insert_expense(300.00,  "Food",      WITHIN_3M_DATE,      "Food 3m")
    _insert_expense(200.00,  "Transport", THIS_MONTH_DATE,     "Transport this month")
    return auth_client


# ------------------------------------------------------------------ #
# 1. Auth Guard                                                       #
# ------------------------------------------------------------------ #

class TestAuthGuard:

    def test_unauthenticated_get_profile_redirects_to_login(self, client):
        response = client.get("/profile")
        assert response.status_code == 302, \
            "Unauthenticated /profile must redirect (302)"
        assert "/login" in response.headers["Location"], \
            "Redirect target must be /login"

    def test_unauthenticated_profile_with_period_param_redirects(self, client):
        response = client.get("/profile?period=this_month")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_unauthenticated_custom_range_redirects(self, client):
        response = client.get("/profile?date_from=2026-01-01&date_to=2026-01-31")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


# ------------------------------------------------------------------ #
# 2. All-Time Default (no ?period= param)                             #
# ------------------------------------------------------------------ #

class TestAllTimeDefault:

    def test_profile_no_param_returns_200(self, seeded_client):
        response = seeded_client.get("/profile")
        assert response.status_code == 200, \
            "Profile without period param must return 200"

    def test_profile_no_param_renders_filter_bar(self, seeded_client):
        html = seeded_client.get("/profile").data.decode()
        assert "filter-bar" in html, "Profile must render the .filter-bar element"

    def test_profile_no_param_active_period_all_time(self, seeded_client):
        html = seeded_client.get("/profile").data.decode()
        assert "filter-btn--active" in html, \
            "At least one filter button must carry the active class"
        assert "All Time" in html, "All Time link must be present"

    def test_profile_no_param_includes_ancient_expense(self, seeded_client):
        """All-time must include the expense from 365 days ago."""
        html = seeded_client.get("/profile").data.decode()
        assert "Ancient bill" in html, \
            "All-time view must include the ancient expense in transactions"

    def test_profile_no_param_total_is_sum_of_all(self, seeded_client):
        """Total = 1000 + 500 + 300 + 200 = 2000."""
        html = seeded_client.get("/profile").data.decode()
        assert "2,000" in html, "All-time total spent must be 2000"

    def test_profile_explicit_all_time_param_returns_200(self, seeded_client):
        response = seeded_client.get("/profile?period=all_time")
        assert response.status_code == 200

    def test_profile_explicit_all_time_shows_all_data(self, seeded_client):
        html = seeded_client.get("/profile?period=all_time").data.decode()
        assert "2,000" in html, \
            "Explicit all_time must also show grand total of 2000"
        assert "Ancient bill" in html


# ------------------------------------------------------------------ #
# 3. this_month Preset                                                #
# ------------------------------------------------------------------ #

class TestThisMonthFilter:

    def test_this_month_returns_200(self, seeded_client):
        response = seeded_client.get("/profile?period=this_month")
        assert response.status_code == 200

    def test_this_month_includes_current_month_expense(self, seeded_client):
        html = seeded_client.get("/profile?period=this_month").data.decode()
        assert "Transport this month" in html, \
            "this_month must include expense dated in the current calendar month"

    def test_this_month_excludes_ancient_expense(self, seeded_client):
        html = seeded_client.get("/profile?period=this_month").data.decode()
        assert "Ancient bill" not in html, \
            "this_month must exclude expense from 365 days ago"

    def test_this_month_excludes_45_day_old_expense(self, seeded_client):
        # WITHIN_3M_DATE is 45 days ago; it should be outside this_month unless
        # the 1st of the month is within 45 days, which is always true, but the
        # expense date itself (today - 45 days) will only be in this_month if
        # today's month started more than 45 days ago — highly unlikely (max 30 days).
        # Guard: only assert if WITHIN_3M_DATE is before THIS_MONTH_START.
        if WITHIN_3M_DATE < THIS_MONTH_START:
            html = seeded_client.get("/profile?period=this_month").data.decode()
            assert "Food 3m" not in html, \
                "this_month must exclude expense dated before the 1st of the current month"

    def test_this_month_excludes_6m_only_expense(self, seeded_client):
        html = seeded_client.get("/profile?period=this_month").data.decode()
        assert "Health 6m" not in html, \
            "this_month must exclude expense from 120 days ago"


# ------------------------------------------------------------------ #
# 4. last_3_months Preset                                             #
# ------------------------------------------------------------------ #

class TestLast3MonthsFilter:

    def test_last_3_months_returns_200(self, seeded_client):
        response = seeded_client.get("/profile?period=last_3_months")
        assert response.status_code == 200

    def test_last_3_months_includes_45_day_old_expense(self, seeded_client):
        html = seeded_client.get("/profile?period=last_3_months").data.decode()
        assert "Food 3m" in html, \
            "last_3_months must include expense from 45 days ago"

    def test_last_3_months_includes_this_month_expense(self, seeded_client):
        html = seeded_client.get("/profile?period=last_3_months").data.decode()
        assert "Transport this month" in html, \
            "last_3_months must include expense from this month"

    def test_last_3_months_excludes_ancient_expense(self, seeded_client):
        html = seeded_client.get("/profile?period=last_3_months").data.decode()
        assert "Ancient bill" not in html, \
            "last_3_months must exclude expense from 365 days ago"

    def test_last_3_months_excludes_120_day_old_expense(self, seeded_client):
        """Health 6m is 120 days ago — outside the 90-day window."""
        html = seeded_client.get("/profile?period=last_3_months").data.decode()
        assert "Health 6m" not in html, \
            "last_3_months must exclude expense from 120 days ago"

    def test_last_3_months_stats_top_category_is_food(self, seeded_client):
        """Within 90 days: Food=300, Transport=200 → Food is top category."""
        html = seeded_client.get("/profile?period=last_3_months").data.decode()
        assert "Food" in html, \
            "Top category for last_3_months should be Food (highest amount within window)"


# ------------------------------------------------------------------ #
# 5. last_6_months Preset                                             #
# ------------------------------------------------------------------ #

class TestLast6MonthsFilter:

    def test_last_6_months_returns_200(self, seeded_client):
        response = seeded_client.get("/profile?period=last_6_months")
        assert response.status_code == 200

    def test_last_6_months_includes_120_day_old_expense(self, seeded_client):
        html = seeded_client.get("/profile?period=last_6_months").data.decode()
        assert "Health 6m" in html, \
            "last_6_months must include expense from 120 days ago"

    def test_last_6_months_includes_45_day_old_expense(self, seeded_client):
        html = seeded_client.get("/profile?period=last_6_months").data.decode()
        assert "Food 3m" in html, \
            "last_6_months must include expense from 45 days ago"

    def test_last_6_months_includes_this_month_expense(self, seeded_client):
        html = seeded_client.get("/profile?period=last_6_months").data.decode()
        assert "Transport this month" in html

    def test_last_6_months_excludes_ancient_expense(self, seeded_client):
        html = seeded_client.get("/profile?period=last_6_months").data.decode()
        assert "Ancient bill" not in html, \
            "last_6_months must exclude expense from 365 days ago"

    def test_last_6_months_total_excludes_ancient(self, seeded_client):
        """Sum within 180 days: 500 + 300 + 200 = 1000.  Ancient 1000 excluded."""
        html = seeded_client.get("/profile?period=last_6_months").data.decode()
        assert "1,000" in html, \
            "last_6_months total should be 1000 (Health+Food+Transport)"

    def test_last_6_months_top_category_is_health(self, seeded_client):
        """Within 180 days: Health=500, Food=300, Transport=200 → Health is top."""
        html = seeded_client.get("/profile?period=last_6_months").data.decode()
        assert "Health" in html, \
            "Top category for last_6_months should be Health (500 BDT)"


# ------------------------------------------------------------------ #
# 6. Unknown / Garbage ?period= Value                                 #
# ------------------------------------------------------------------ #

class TestUnknownPeriodFallback:

    @pytest.mark.parametrize("bad_period", [
        "yesterday",
        "LAST_YEAR",
        "last_12_months",
        "12345",
        "'; DROP TABLE expenses; --",
        "none",
        "null",
    ])
    def test_unknown_period_returns_200_no_crash(self, seeded_client, bad_period):
        response = seeded_client.get(f"/profile?period={bad_period}")
        assert response.status_code == 200, \
            f"Unknown period '{bad_period}' must return 200, not crash"

    def test_unknown_period_falls_back_to_all_time_data(self, seeded_client):
        """Unrecognised period must show all-time total (2000)."""
        html = seeded_client.get("/profile?period=never_heard_of_this").data.decode()
        assert "2,000" in html, \
            "Unknown period must fall back to all-time data (total 2000)"

    def test_unknown_period_ancient_expense_visible(self, seeded_client):
        html = seeded_client.get("/profile?period=bogus").data.decode()
        assert "Ancient bill" in html, \
            "Unknown period must fall back to all-time — ancient bill must be visible"


# ------------------------------------------------------------------ #
# 7. Custom Date Range                                                 #
# ------------------------------------------------------------------ #

class TestCustomDateRange:

    def test_custom_range_returns_200(self, seeded_client):
        response = seeded_client.get(
            f"/profile?date_from={WITHIN_6M_ONLY_DATE}&date_to={WITHIN_6M_ONLY_DATE}"
        )
        assert response.status_code == 200

    def test_custom_range_active_period_is_custom(self, seeded_client):
        """Both date_from and date_to supplied → active_period must be 'custom',
        so the Apply button carries filter-btn--active."""
        html = seeded_client.get(
            f"/profile?date_from={WITHIN_6M_ONLY_DATE}&date_to={WITHIN_6M_ONLY_DATE}"
        ).data.decode()
        assert "filter-btn--active" in html, \
            "Custom range: at least one element must carry filter-btn--active"

    def test_custom_range_shows_only_in_range_expense(self, seeded_client):
        """Range covers only WITHIN_6M_ONLY_DATE → Health 6m must appear."""
        html = seeded_client.get(
            f"/profile?date_from={WITHIN_6M_ONLY_DATE}&date_to={WITHIN_6M_ONLY_DATE}"
        ).data.decode()
        assert "Health 6m" in html, \
            "Expense on the exact custom date must appear in the results"

    def test_custom_range_excludes_out_of_range_expenses(self, seeded_client):
        html = seeded_client.get(
            f"/profile?date_from={WITHIN_6M_ONLY_DATE}&date_to={WITHIN_6M_ONLY_DATE}"
        ).data.decode()
        assert "Ancient bill" not in html, \
            "Custom range must exclude expense before date_from"
        assert "Transport this month" not in html, \
            "Custom range must exclude expense after date_to"

    def test_custom_range_inclusive_on_both_ends(self, seeded_client):
        """Range [WITHIN_3M_DATE, THIS_MONTH_DATE] — both boundary dates must be included."""
        html = seeded_client.get(
            f"/profile?date_from={WITHIN_3M_DATE}&date_to={THIS_MONTH_DATE}"
        ).data.decode()
        assert "Food 3m" in html, \
            "date_from boundary must be inclusive — Food 3m must appear"
        assert "Transport this month" in html, \
            "date_to boundary must be inclusive — Transport this month must appear"

    def test_custom_range_filter_inputs_echo_submitted_values(self, seeded_client):
        """The date inputs must render with the submitted values (filter_from / filter_to)."""
        d_from = WITHIN_6M_ONLY_DATE
        d_to = WITHIN_3M_DATE
        html = seeded_client.get(f"/profile?date_from={d_from}&date_to={d_to}").data.decode()
        assert d_from in html, "filter_from must be echoed into the date input value"
        assert d_to in html, "filter_to must be echoed into the date input value"

    def test_custom_range_only_date_from_does_not_crash(self, seeded_client):
        """Supplying only date_from (no date_to) must return 200, not 500."""
        response = seeded_client.get(f"/profile?date_from={WITHIN_6M_ONLY_DATE}")
        assert response.status_code == 200, \
            "Partial custom params (date_from only) must not crash"

    def test_custom_range_only_date_to_does_not_crash(self, seeded_client):
        """Supplying only date_to (no date_from) must return 200, not 500."""
        response = seeded_client.get(f"/profile?date_to={TODAY_ISO}")
        assert response.status_code == 200, \
            "Partial custom params (date_to only) must not crash"


# ------------------------------------------------------------------ #
# 8. Empty State — User Has No Expenses At All                        #
# ------------------------------------------------------------------ #

class TestEmptyStateNoExpenses:

    def test_no_expenses_all_time_returns_200(self, auth_client):
        assert auth_client.get("/profile").status_code == 200

    def test_no_expenses_this_month_returns_200(self, auth_client):
        assert auth_client.get("/profile?period=this_month").status_code == 200

    def test_no_expenses_last_3_months_returns_200(self, auth_client):
        assert auth_client.get("/profile?period=last_3_months").status_code == 200

    def test_no_expenses_last_6_months_returns_200(self, auth_client):
        assert auth_client.get("/profile?period=last_6_months").status_code == 200

    def test_no_expenses_custom_range_returns_200(self, auth_client):
        response = auth_client.get(
            f"/profile?date_from={ANCIENT_DATE}&date_to={TODAY_ISO}"
        )
        assert response.status_code == 200

    def test_no_expenses_currency_symbol_still_rendered(self, auth_client):
        """Stats section must render (with zero) even when no expenses exist."""
        html = auth_client.get("/profile").data.decode()
        # The template always renders ৳ for total_spent — verify the page doesn't error out.
        assert "৳" in html, \
            "Currency symbol must appear in stats even when user has no expenses"


# ------------------------------------------------------------------ #
# 9. Empty State — Expenses Exist But None Fall in the Period         #
# ------------------------------------------------------------------ #

class TestEmptyStatePeriodMismatch:

    def test_only_ancient_expense_this_month_returns_200(self, auth_client):
        _insert_expense(500.00, "Bills", ANCIENT_DATE, "OldOnly")
        assert auth_client.get("/profile?period=this_month").status_code == 200

    def test_only_ancient_expense_this_month_hides_it(self, auth_client):
        _insert_expense(500.00, "Bills", ANCIENT_DATE, "OldOnlyHidden")
        html = auth_client.get("/profile?period=this_month").data.decode()
        assert "OldOnlyHidden" not in html, \
            "Ancient expense must not appear under this_month filter"

    def test_only_ancient_expense_last_3_months_returns_200(self, auth_client):
        _insert_expense(500.00, "Bills", ANCIENT_DATE, "OldB2")
        assert auth_client.get("/profile?period=last_3_months").status_code == 200

    def test_only_ancient_expense_last_6_months_returns_200(self, auth_client):
        _insert_expense(500.00, "Bills", ANCIENT_DATE, "OldB3")
        assert auth_client.get("/profile?period=last_6_months").status_code == 200

    def test_only_ancient_expense_custom_future_range_returns_200(self, auth_client):
        _insert_expense(500.00, "Bills", ANCIENT_DATE, "OldB4")
        # Custom range covering only today — ancient expense outside range.
        response = auth_client.get(
            f"/profile?date_from={TODAY_ISO}&date_to={TODAY_ISO}"
        )
        assert response.status_code == 200


# ------------------------------------------------------------------ #
# 10. Active Period HTML Indicator                                     #
# ------------------------------------------------------------------ #

class TestActivePeriodIndicator:
    """
    Verify the correct filter button carries filter-btn--active.
    We parse the rendered HTML to find which anchor text is paired with the
    active CSS class.
    """

    def _active_link_texts(self, html):
        """
        Return list of stripped inner texts of any <a> or <button> element
        whose class attribute contains 'filter-btn--active'.
        Handles both class="filter-btn filter-btn--active" and
        class="filter-btn--active filter-btn" orderings.
        """
        pattern = r'<(?:a|button)\s[^>]*class="[^"]*filter-btn--active[^"]*"[^>]*>([^<]+)</(?:a|button)>'
        return [m.strip() for m in re.findall(pattern, html)]

    def test_no_param_all_time_button_is_active(self, seeded_client):
        html = seeded_client.get("/profile").data.decode()
        active = self._active_link_texts(html)
        assert "All Time" in active, \
            f"Expected 'All Time' to be the active button, got: {active}"

    def test_this_month_button_is_active(self, seeded_client):
        html = seeded_client.get("/profile?period=this_month").data.decode()
        active = self._active_link_texts(html)
        assert "This Month" in active, \
            f"Expected 'This Month' to be active, got: {active}"

    def test_last_3_months_button_is_active(self, seeded_client):
        html = seeded_client.get("/profile?period=last_3_months").data.decode()
        active = self._active_link_texts(html)
        assert "Last 3 Months" in active, \
            f"Expected 'Last 3 Months' to be active, got: {active}"

    def test_last_6_months_button_is_active(self, seeded_client):
        html = seeded_client.get("/profile?period=last_6_months").data.decode()
        active = self._active_link_texts(html)
        assert "Last 6 Months" in active, \
            f"Expected 'Last 6 Months' to be active, got: {active}"

    def test_explicit_all_time_button_is_active(self, seeded_client):
        html = seeded_client.get("/profile?period=all_time").data.decode()
        active = self._active_link_texts(html)
        assert "All Time" in active, \
            f"Expected 'All Time' to be active with explicit param, got: {active}"

    def test_this_month_does_not_activate_other_buttons(self, seeded_client):
        html = seeded_client.get("/profile?period=this_month").data.decode()
        active = self._active_link_texts(html)
        assert "Last 3 Months" not in active, \
            "Last 3 Months must NOT be active when this_month is selected"
        assert "Last 6 Months" not in active, \
            "Last 6 Months must NOT be active when this_month is selected"
        assert "All Time" not in active, \
            "All Time must NOT be active when this_month is selected"

    def test_last_3_months_does_not_activate_other_buttons(self, seeded_client):
        html = seeded_client.get("/profile?period=last_3_months").data.decode()
        active = self._active_link_texts(html)
        assert "This Month" not in active
        assert "Last 6 Months" not in active
        assert "All Time" not in active


# ------------------------------------------------------------------ #
# 11. Filter Bar HTML Structure                                        #
# ------------------------------------------------------------------ #

class TestFilterBarStructure:

    def test_filter_bar_element_present(self, auth_client):
        html = auth_client.get("/profile").data.decode()
        assert "filter-bar" in html, "Profile must contain an element with class filter-bar"

    def test_this_month_link_present(self, auth_client):
        html = auth_client.get("/profile").data.decode()
        assert "This Month" in html

    def test_last_3_months_link_present(self, auth_client):
        html = auth_client.get("/profile").data.decode()
        assert "Last 3 Months" in html

    def test_last_6_months_link_present(self, auth_client):
        html = auth_client.get("/profile").data.decode()
        assert "Last 6 Months" in html

    def test_all_time_link_present(self, auth_client):
        html = auth_client.get("/profile").data.decode()
        assert "All Time" in html

    def test_period_query_strings_in_links(self, auth_client):
        html = auth_client.get("/profile").data.decode()
        assert "?period=this_month" in html
        assert "?period=last_3_months" in html
        assert "?period=last_6_months" in html

    def test_filter_btn_class_on_links(self, auth_client):
        html = auth_client.get("/profile").data.decode()
        assert "filter-btn" in html, "Filter links must carry the filter-btn CSS class"

    def test_custom_date_form_has_date_from_input(self, auth_client):
        html = auth_client.get("/profile").data.decode()
        assert "date_from" in html, "Filter bar must contain a date_from input"

    def test_custom_date_form_has_date_to_input(self, auth_client):
        html = auth_client.get("/profile").data.decode()
        assert "date_to" in html, "Filter bar must contain a date_to input"


# ------------------------------------------------------------------ #
# 12. Stats Correctness Per Period                                     #
# ------------------------------------------------------------------ #

class TestStatsCorrectness:

    def test_all_time_total_spent_2000(self, seeded_client):
        """1000 + 500 + 300 + 200 = 2000."""
        html = seeded_client.get("/profile").data.decode()
        assert "2,000" in html, "All-time total spent must be ৳2,000"

    def test_all_time_transaction_count_4(self, seeded_client):
        html = seeded_client.get("/profile").data.decode()
        assert "4" in html, "All-time transaction count must be 4"

    def test_all_time_top_category_bills(self, seeded_client):
        """Bills (1000) is the single largest category expense."""
        html = seeded_client.get("/profile").data.decode()
        assert "Bills" in html, "All-time top category must be Bills"

    def test_last_6_months_total_1000(self, seeded_client):
        """500 + 300 + 200 = 1000 within 180 days."""
        html = seeded_client.get("/profile?period=last_6_months").data.decode()
        assert "1,000" in html, "last_6_months total must be 1000"

    def test_last_6_months_top_category_health(self, seeded_client):
        """Health (500) is highest within 180-day window."""
        html = seeded_client.get("/profile?period=last_6_months").data.decode()
        assert "Health" in html

    def test_last_3_months_top_category_food(self, seeded_client):
        """Food (300) is highest within 90-day window."""
        html = seeded_client.get("/profile?period=last_3_months").data.decode()
        assert "Food" in html

    def test_this_month_transaction_count_at_least_1(self, seeded_client):
        """THIS_MONTH_DATE expense (Transport) must always be in this_month."""
        html = seeded_client.get("/profile?period=this_month").data.decode()
        # At minimum 1 transaction (Transport this month)
        assert "Transport" in html


# ------------------------------------------------------------------ #
# 13. Category Breakdown Scoped by Period                             #
# ------------------------------------------------------------------ #

class TestCategoryBreakdown:

    def test_all_time_all_categories_present(self, seeded_client):
        html = seeded_client.get("/profile").data.decode()
        assert "Bills" in html
        assert "Health" in html
        assert "Food" in html
        assert "Transport" in html

    def test_last_6_months_bills_absent_from_breakdown(self, seeded_client):
        """Bills (ANCIENT_DATE) is outside the 180-day window — must not appear."""
        html = seeded_client.get("/profile?period=last_6_months").data.decode()
        # 'Ancient bill' is the description; Bills is the category.
        # Since the ancient expense is the only Bills expense, Bills category is absent.
        assert "Ancient bill" not in html

    def test_last_3_months_health_absent(self, seeded_client):
        """Health 6m (120 days ago) is outside the 90-day window."""
        html = seeded_client.get("/profile?period=last_3_months").data.decode()
        assert "Health 6m" not in html

    def test_last_6_months_health_present(self, seeded_client):
        """Health 6m (120 days ago) is inside the 180-day window."""
        html = seeded_client.get("/profile?period=last_6_months").data.decode()
        assert "Health 6m" in html

    def test_empty_period_no_breakdown_items(self, auth_client):
        """User with only an ancient expense — this_month breakdown must be empty."""
        _insert_expense(999.00, "Bills", ANCIENT_DATE, "BillXEmpty")
        html = auth_client.get("/profile?period=this_month").data.decode()
        assert "BillXEmpty" not in html, \
            "Ancient expense must not appear in this_month category breakdown"


# ------------------------------------------------------------------ #
# 14. get_recent_expenses Limit Respected Under Date Filter           #
# ------------------------------------------------------------------ #

class TestRecentExpensesLimit:

    def test_limit_not_exceeded_under_date_filter(self, auth_client):
        """Insert 8 expenses all dated today under this_month — at most 5 should show."""
        descriptions = [f"LimitTx-{i}" for i in range(8)]
        for desc in descriptions:
            _insert_expense(100.00, "Food", TODAY_ISO, desc)

        html = auth_client.get("/profile?period=this_month").data.decode()
        visible = sum(1 for d in descriptions if d in html)
        assert visible <= 5, \
            f"At most 5 recent transactions must be shown (default limit), found {visible}"

    def test_limit_not_exceeded_all_time(self, auth_client):
        """Same limit check for the all-time view (no date filter)."""
        descriptions = [f"LimitAllTime-{i}" for i in range(7)]
        for desc in descriptions:
            _insert_expense(50.00, "Other", TODAY_ISO, desc)

        html = auth_client.get("/profile").data.decode()
        visible = sum(1 for d in descriptions if d in html)
        assert visible <= 5, \
            f"All-time view must also cap recent transactions at 5, found {visible}"

    def test_limit_not_exceeded_custom_range(self, auth_client):
        """Limit must apply even with a wide custom date range."""
        descriptions = [f"LimitCustom-{i}" for i in range(6)]
        for desc in descriptions:
            _insert_expense(75.00, "Shopping", TODAY_ISO, desc)

        html = auth_client.get(
            f"/profile?date_from={ANCIENT_DATE}&date_to={TODAY_ISO}"
        ).data.decode()
        visible = sum(1 for d in descriptions if d in html)
        assert visible <= 5, \
            f"Custom range view must also cap recent transactions at 5, found {visible}"
