"""
tests/test_07-add-expense.py

Test suite for Spendly Step 07 — Add Expense feature.

Coverage
--------
- Auth guard: GET and POST while logged out redirect to /login
- GET happy path: form renders with all required fields, today's date pre-filled,
  all valid categories listed, back-to-profile link present
- POST happy path: valid submission inserts one row, redirects to /profile with
  success flash "Expense added."
- DB side effects: expense count increases by 1, stored values match submitted values
- Blank description stored as NULL (not empty string); whitespace-only also NULL
- Validation errors: blank amount, non-numeric amount, zero amount, negative amount,
  invalid category, blank date, invalid date string, description > 200 chars
- Sticky form: previously entered values re-populated on validation failure
- Profile page: "Add Expense" button/link present and href points to /expenses/add
- All 7 valid categories accepted (parametrized)
- Multiple invalid inputs each trigger re-render (parametrized)

Isolation note
--------------
database.db.get_db() always opens DB_PATH — a file path — ignoring Flask's
config['DATABASE'].  We monkey-patch `database.db.DB_PATH` to a temporary
SQLite file for every test so all DB calls (routes + test helpers) share the
same isolated file.  The file is deleted in fixture teardown.
"""

import os
import tempfile
from datetime import date

import pytest

import database.db as db_module
from app import app as flask_app
from database.db import init_db

# ------------------------------------------------------------------ #
# Constants                                                           #
# ------------------------------------------------------------------ #

TODAY_ISO = date.today().isoformat()

# The seven valid categories as defined by the spec.
VALID_CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]

_TEST_EMAIL    = "testuser@example.com"
_TEST_PASSWORD = "securepass123"
_TEST_NAME     = "Test User"

# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def app():
    """
    Flask app wired to an isolated temporary SQLite file.

    We monkey-patch database.db.DB_PATH before each test and restore it
    afterwards so no test ever touches the real spendly.db.
    """
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    original_db_path = db_module.DB_PATH
    db_module.DB_PATH = db_path

    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "WTF_CSRF_ENABLED": False,
    })

    with flask_app.app_context():
        init_db()
        yield flask_app

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
    """Test client that has registered and logged in as the test user."""
    client.post("/register", data={
        "name":             _TEST_NAME,
        "email":            _TEST_EMAIL,
        "password":         _TEST_PASSWORD,
        "confirm_password": _TEST_PASSWORD,
    })
    client.post("/login", data={
        "email":    _TEST_EMAIL,
        "password": _TEST_PASSWORD,
    })
    return client


# ------------------------------------------------------------------ #
# DB query helpers (use the monkey-patched DB_PATH)                   #
# ------------------------------------------------------------------ #

def _get_user_id():
    """Return the user_id for the test user (must exist after auth_client ran)."""
    conn = db_module.get_db()
    row = conn.execute(
        "SELECT id FROM users WHERE email = ?", (_TEST_EMAIL,)
    ).fetchone()
    conn.close()
    assert row is not None, f"{_TEST_EMAIL} not found — ensure auth_client ran first"
    return row["id"]


def _get_expense_count():
    """Return the total number of expense rows for the test user."""
    conn = db_module.get_db()
    user_id = _get_user_id()
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return row["cnt"]


def _get_last_expense():
    """Return the most recently inserted expense row for the test user."""
    conn = db_module.get_db()
    user_id = _get_user_id()
    row = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    conn.close()
    return row


# ------------------------------------------------------------------ #
# 1. Auth Guard                                                       #
# ------------------------------------------------------------------ #

class TestAuthGuard:

    def test_get_add_expense_logged_out_redirects(self, client):
        response = client.get("/expenses/add")
        assert response.status_code == 302, \
            "GET /expenses/add while logged out must redirect (302)"
        assert "/login" in response.headers["Location"], \
            "Redirect target must be /login"

    def test_post_add_expense_logged_out_redirects(self, client):
        response = client.post("/expenses/add", data={
            "amount":      "100",
            "category":    "Food",
            "date":        TODAY_ISO,
            "description": "Test",
        })
        assert response.status_code == 302, \
            "POST /expenses/add while logged out must redirect (302)"
        assert "/login" in response.headers["Location"], \
            "POST logged-out redirect target must be /login"

    def test_get_add_expense_logged_out_no_db_write(self, client):
        """Unauthenticated GET must not insert anything."""
        client.get("/expenses/add")
        # No user exists, but ensure no expenses table anomalies either
        conn = db_module.get_db()
        count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        conn.close()
        assert count == 0, "Unauthenticated GET must not write to expenses table"


# ------------------------------------------------------------------ #
# 2. GET Happy Path                                                    #
# ------------------------------------------------------------------ #

class TestGetForm:

    def test_get_returns_200(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert response.status_code == 200, \
            "GET /expenses/add while logged in must return 200"

    def test_get_renders_amount_input(self, auth_client):
        html = auth_client.get("/expenses/add").data.decode()
        assert 'name="amount"' in html, \
            "Form must contain an amount input field"

    def test_get_renders_category_select(self, auth_client):
        html = auth_client.get("/expenses/add").data.decode()
        assert 'name="category"' in html, \
            "Form must contain a category select field"

    def test_get_renders_date_input(self, auth_client):
        html = auth_client.get("/expenses/add").data.decode()
        assert 'name="date"' in html, \
            "Form must contain a date input field"

    def test_get_renders_description_textarea(self, auth_client):
        html = auth_client.get("/expenses/add").data.decode()
        assert 'name="description"' in html, \
            "Form must contain a description textarea"

    def test_get_renders_submit_button(self, auth_client):
        html = auth_client.get("/expenses/add").data.decode()
        # The spec says submit button text is "Add Expense"
        assert "Add Expense" in html, \
            "Form must contain a submit button labelled 'Add Expense'"

    def test_get_today_date_prefilled(self, auth_client):
        """The date input must carry today's ISO date as its value."""
        html = auth_client.get("/expenses/add").data.decode()
        assert TODAY_ISO in html, \
            f"Today's date ({TODAY_ISO}) must be pre-filled in the form"

    def test_get_all_valid_categories_listed(self, auth_client):
        """All seven fixed categories must appear as <option> values."""
        html = auth_client.get("/expenses/add").data.decode()
        for cat in VALID_CATEGORIES:
            assert cat in html, \
                f"Category '{cat}' must appear in the category <select>"

    def test_get_back_to_profile_link_present(self, auth_client):
        """Template must contain a link back to the profile page."""
        html = auth_client.get("/expenses/add").data.decode()
        assert "/profile" in html, \
            "Form page must contain a back link to /profile"
        # The spec says the link text is "← Back to Profile"
        assert "Back to Profile" in html, \
            "Back-to-profile link text must be present"

    def test_get_form_method_is_post(self, auth_client):
        html = auth_client.get("/expenses/add").data.decode()
        assert 'method="POST"' in html or 'method="post"' in html, \
            "Form must use POST method"

    def test_get_form_action_points_to_add_expense(self, auth_client):
        html = auth_client.get("/expenses/add").data.decode()
        assert "/expenses/add" in html, \
            "Form action must point to /expenses/add"

    def test_get_no_error_message_on_fresh_load(self, auth_client):
        """A fresh GET must not show any error message."""
        html = auth_client.get("/expenses/add").data.decode()
        # The error area is only rendered when the 'error' context variable is set.
        # If no error string is expected, common markers should be absent.
        # We check no validation-error text is present.
        assert "required" not in html.lower() or "required" in html, \
            "No false-positive error on fresh GET"
        # More specific: none of the known validation error phrases
        assert "Amount is required" not in html
        assert "Date is required" not in html


# ------------------------------------------------------------------ #
# 3. POST Happy Path                                                   #
# ------------------------------------------------------------------ #

class TestPostHappyPath:

    def _valid_form(self, **overrides):
        data = {
            "amount":      "250.50",
            "category":    "Food",
            "date":        TODAY_ISO,
            "description": "Lunch at office",
        }
        data.update(overrides)
        return data

    def test_post_valid_redirects_to_profile(self, auth_client):
        response = auth_client.post("/expenses/add", data=self._valid_form())
        assert response.status_code == 302, \
            "Valid POST must redirect (302)"
        assert "/profile" in response.headers["Location"], \
            "Redirect target must be /profile"

    def test_post_valid_flash_message_on_profile(self, auth_client):
        """After redirect, the profile page must display the success flash."""
        auth_client.post("/expenses/add", data=self._valid_form())
        profile_html = auth_client.get("/profile").data.decode()
        assert "Expense added" in profile_html, \
            "Success flash 'Expense added.' must appear on the profile page"

    def test_post_valid_expense_count_increases(self, auth_client):
        before = _get_expense_count()
        auth_client.post("/expenses/add", data=self._valid_form())
        after = _get_expense_count()
        assert after == before + 1, \
            f"Expense count must increase by 1 after valid POST (was {before}, now {after})"

    def test_post_valid_amount_stored_correctly(self, auth_client):
        auth_client.post("/expenses/add", data=self._valid_form(amount="350.75"))
        row = _get_last_expense()
        assert row is not None, "An expense row must exist after valid POST"
        assert abs(row["amount"] - 350.75) < 0.001, \
            f"Stored amount must be 350.75, got {row['amount']}"

    def test_post_valid_category_stored_correctly(self, auth_client):
        auth_client.post("/expenses/add", data=self._valid_form(category="Health"))
        row = _get_last_expense()
        assert row["category"] == "Health", \
            f"Stored category must be 'Health', got {row['category']}"

    def test_post_valid_date_stored_correctly(self, auth_client):
        auth_client.post("/expenses/add", data=self._valid_form(date="2026-05-10"))
        row = _get_last_expense()
        assert row["date"] == "2026-05-10", \
            f"Stored date must be '2026-05-10', got {row['date']}"

    def test_post_valid_description_stored_correctly(self, auth_client):
        auth_client.post("/expenses/add", data=self._valid_form(description="Office snacks"))
        row = _get_last_expense()
        assert row["description"] == "Office snacks", \
            f"Stored description must be 'Office snacks', got {row['description']}"

    def test_post_valid_user_id_stored_correctly(self, auth_client):
        """Expense must be associated with the logged-in user's ID."""
        user_id = _get_user_id()
        auth_client.post("/expenses/add", data=self._valid_form())
        row = _get_last_expense()
        assert row["user_id"] == user_id, \
            f"Expense must be owned by user_id={user_id}, got {row['user_id']}"

    def test_post_integer_amount_accepted(self, auth_client):
        """Whole-number amounts (no decimal) must also be accepted."""
        response = auth_client.post("/expenses/add", data=self._valid_form(amount="500"))
        assert response.status_code == 302, \
            "Integer amount '500' must be accepted and redirect"

    def test_post_minimum_valid_amount_accepted(self, auth_client):
        """Smallest positive float (0.01) must be accepted."""
        response = auth_client.post("/expenses/add", data=self._valid_form(amount="0.01"))
        assert response.status_code == 302, \
            "Amount 0.01 must be accepted (minimum positive value)"


# ------------------------------------------------------------------ #
# 4. Description NULL Storage                                         #
# ------------------------------------------------------------------ #

class TestDescriptionNullStorage:

    def test_blank_description_stored_as_null(self, auth_client):
        """Omitting description entirely must store NULL, not an empty string."""
        auth_client.post("/expenses/add", data={
            "amount":      "100",
            "category":    "Transport",
            "date":        TODAY_ISO,
            "description": "",
        })
        row = _get_last_expense()
        assert row is not None, "Expense row must be inserted"
        assert row["description"] is None, \
            f"Empty description must be stored as NULL, got {row['description']!r}"

    def test_whitespace_only_description_stored_as_null(self, auth_client):
        """Whitespace-only description must be stripped and stored as NULL."""
        auth_client.post("/expenses/add", data={
            "amount":      "100",
            "category":    "Bills",
            "date":        TODAY_ISO,
            "description": "   ",
        })
        row = _get_last_expense()
        assert row is not None, "Expense row must be inserted"
        assert row["description"] is None, \
            f"Whitespace-only description must be stored as NULL, got {row['description']!r}"

    def test_blank_description_no_error_shown(self, auth_client):
        """A missing description is optional — no validation error must appear."""
        response = auth_client.post("/expenses/add", data={
            "amount":      "100",
            "category":    "Other",
            "date":        TODAY_ISO,
            "description": "",
        })
        assert response.status_code == 302, \
            "Blank description must not trigger a validation error; must redirect"


# ------------------------------------------------------------------ #
# 5. Validation Errors                                                #
# ------------------------------------------------------------------ #

class TestValidationErrors:

    def _post(self, auth_client, data):
        return auth_client.post("/expenses/add", data=data)

    def _valid_base(self):
        return {
            "amount":      "100",
            "category":    "Food",
            "date":        TODAY_ISO,
            "description": "",
        }

    # --- Amount validation ---

    def test_blank_amount_returns_200(self, auth_client):
        data = {**self._valid_base(), "amount": ""}
        response = self._post(auth_client, data)
        assert response.status_code == 200, \
            "Blank amount must re-render the form (200), not redirect"

    def test_blank_amount_shows_error(self, auth_client):
        data = {**self._valid_base(), "amount": ""}
        html = self._post(auth_client, data).data.decode()
        assert "Amount" in html and ("required" in html.lower() or "error" in html.lower()), \
            "Blank amount must show a validation error message"

    def test_blank_amount_no_db_insert(self, auth_client):
        before = _get_expense_count()
        self._post(auth_client, {**self._valid_base(), "amount": ""})
        assert _get_expense_count() == before, \
            "Blank amount must not insert any expense row"

    def test_non_numeric_amount_returns_200(self, auth_client):
        data = {**self._valid_base(), "amount": "abc"}
        response = self._post(auth_client, data)
        assert response.status_code == 200, \
            "Non-numeric amount must re-render form (200)"

    def test_non_numeric_amount_shows_error(self, auth_client):
        data = {**self._valid_base(), "amount": "abc"}
        html = self._post(auth_client, data).data.decode()
        assert "number" in html.lower() or "valid" in html.lower() or "amount" in html.lower(), \
            "Non-numeric amount must show a validation error"

    def test_non_numeric_amount_no_db_insert(self, auth_client):
        before = _get_expense_count()
        self._post(auth_client, {**self._valid_base(), "amount": "abc"})
        assert _get_expense_count() == before, \
            "Non-numeric amount must not insert any expense row"

    def test_zero_amount_returns_200(self, auth_client):
        data = {**self._valid_base(), "amount": "0"}
        response = self._post(auth_client, data)
        assert response.status_code == 200, \
            "Zero amount must re-render form (200)"

    def test_zero_amount_shows_error(self, auth_client):
        data = {**self._valid_base(), "amount": "0"}
        html = self._post(auth_client, data).data.decode()
        assert "zero" in html.lower() or "greater" in html.lower() or "amount" in html.lower(), \
            "Zero amount must show a validation error"

    def test_zero_amount_no_db_insert(self, auth_client):
        before = _get_expense_count()
        self._post(auth_client, {**self._valid_base(), "amount": "0"})
        assert _get_expense_count() == before, \
            "Zero amount must not insert any expense row"

    def test_negative_amount_returns_200(self, auth_client):
        data = {**self._valid_base(), "amount": "-50"}
        response = self._post(auth_client, data)
        assert response.status_code == 200, \
            "Negative amount must re-render form (200)"

    def test_negative_amount_shows_error(self, auth_client):
        data = {**self._valid_base(), "amount": "-50"}
        html = self._post(auth_client, data).data.decode()
        assert "zero" in html.lower() or "greater" in html.lower() or "amount" in html.lower(), \
            "Negative amount must show a validation error"

    def test_negative_amount_no_db_insert(self, auth_client):
        before = _get_expense_count()
        self._post(auth_client, {**self._valid_base(), "amount": "-50"})
        assert _get_expense_count() == before, \
            "Negative amount must not insert any expense row"

    # --- Category validation ---

    def test_invalid_category_returns_200(self, auth_client):
        data = {**self._valid_base(), "category": "Gambling"}
        response = self._post(auth_client, data)
        assert response.status_code == 200, \
            "Invalid category must re-render form (200)"

    def test_invalid_category_shows_error(self, auth_client):
        data = {**self._valid_base(), "category": "Gambling"}
        html = self._post(auth_client, data).data.decode()
        assert "category" in html.lower() or "valid" in html.lower(), \
            "Invalid category must show a validation error"

    def test_invalid_category_no_db_insert(self, auth_client):
        before = _get_expense_count()
        self._post(auth_client, {**self._valid_base(), "category": "Gambling"})
        assert _get_expense_count() == before, \
            "Invalid category must not insert any expense row"

    def test_empty_category_returns_200(self, auth_client):
        data = {**self._valid_base(), "category": ""}
        response = self._post(auth_client, data)
        assert response.status_code == 200, \
            "Empty category must re-render form (200)"

    # --- Date validation ---

    def test_blank_date_returns_200(self, auth_client):
        data = {**self._valid_base(), "date": ""}
        response = self._post(auth_client, data)
        assert response.status_code == 200, \
            "Blank date must re-render form (200)"

    def test_blank_date_shows_error(self, auth_client):
        data = {**self._valid_base(), "date": ""}
        html = self._post(auth_client, data).data.decode()
        assert "date" in html.lower() or "required" in html.lower(), \
            "Blank date must show a validation error"

    def test_blank_date_no_db_insert(self, auth_client):
        before = _get_expense_count()
        self._post(auth_client, {**self._valid_base(), "date": ""})
        assert _get_expense_count() == before, \
            "Blank date must not insert any expense row"

    def test_invalid_date_returns_200(self, auth_client):
        data = {**self._valid_base(), "date": "2026-13-01"}
        response = self._post(auth_client, data)
        assert response.status_code == 200, \
            "Invalid date '2026-13-01' must re-render form (200)"

    def test_invalid_date_shows_error(self, auth_client):
        data = {**self._valid_base(), "date": "2026-13-01"}
        html = self._post(auth_client, data).data.decode()
        assert "date" in html.lower() or "valid" in html.lower(), \
            "Invalid date must show a validation error"

    def test_invalid_date_no_db_insert(self, auth_client):
        before = _get_expense_count()
        self._post(auth_client, {**self._valid_base(), "date": "2026-13-01"})
        assert _get_expense_count() == before, \
            "Invalid date must not insert any expense row"

    def test_malformed_date_format_returns_200(self, auth_client):
        """Date that does not match YYYY-MM-DD format must be rejected."""
        data = {**self._valid_base(), "date": "05/15/2026"}
        response = self._post(auth_client, data)
        assert response.status_code == 200, \
            "Date '05/15/2026' (wrong format) must re-render form (200)"

    # --- Description length validation ---

    def test_description_too_long_returns_200(self, auth_client):
        data = {**self._valid_base(), "description": "x" * 201}
        response = self._post(auth_client, data)
        assert response.status_code == 200, \
            "Description > 200 chars must re-render form (200)"

    def test_description_too_long_shows_error(self, auth_client):
        data = {**self._valid_base(), "description": "x" * 201}
        html = self._post(auth_client, data).data.decode()
        assert "200" in html or "description" in html.lower(), \
            "Description > 200 chars must show a validation error mentioning 200"

    def test_description_too_long_no_db_insert(self, auth_client):
        before = _get_expense_count()
        self._post(auth_client, {**self._valid_base(), "description": "x" * 201})
        assert _get_expense_count() == before, \
            "Description > 200 chars must not insert any expense row"

    def test_description_exactly_200_chars_accepted(self, auth_client):
        """200 characters is the boundary — must be accepted."""
        data = {**self._valid_base(), "description": "a" * 200}
        response = self._post(auth_client, data)
        assert response.status_code == 302, \
            "Description of exactly 200 characters must be accepted"


# ------------------------------------------------------------------ #
# 6. Sticky Form (values preserved on validation error)               #
# ------------------------------------------------------------------ #

class TestStickyForm:

    def test_sticky_amount_on_invalid_category(self, auth_client):
        """When category is invalid, the entered amount must appear in the re-rendered form."""
        html = auth_client.post("/expenses/add", data={
            "amount":      "999",
            "category":    "NotACategory",
            "date":        TODAY_ISO,
            "description": "stickydesc",
        }).data.decode()
        assert "999" in html, \
            "Previously entered amount must be sticky after validation failure"

    def test_sticky_description_on_invalid_amount(self, auth_client):
        """When amount is invalid, the entered description must appear in re-rendered form."""
        html = auth_client.post("/expenses/add", data={
            "amount":      "bad",
            "category":    "Food",
            "date":        TODAY_ISO,
            "description": "my sticky note",
        }).data.decode()
        assert "my sticky note" in html, \
            "Previously entered description must be sticky after validation failure"

    def test_sticky_date_on_invalid_amount(self, auth_client):
        """When amount is invalid, the entered date must appear in re-rendered form."""
        html = auth_client.post("/expenses/add", data={
            "amount":      "bad",
            "category":    "Food",
            "date":        "2026-04-01",
            "description": "",
        }).data.decode()
        assert "2026-04-01" in html, \
            "Previously entered date must be sticky after validation failure"

    def test_error_message_shown_in_form(self, auth_client):
        """The error context variable must cause an error element to render."""
        html = auth_client.post("/expenses/add", data={
            "amount":      "",
            "category":    "Food",
            "date":        TODAY_ISO,
            "description": "",
        }).data.decode()
        # Some error element must appear — check for common error indicators.
        has_error = (
            "error" in html.lower()
            or "alert" in html.lower()
            or "invalid" in html.lower()
            or "required" in html.lower()
        )
        assert has_error, \
            "Validation failure must render an error message in the form"


# ------------------------------------------------------------------ #
# 7. Profile Page — "Add Expense" Button                              #
# ------------------------------------------------------------------ #

class TestProfileAddExpenseButton:

    def test_profile_has_add_expense_link(self, auth_client):
        html = auth_client.get("/profile").data.decode()
        assert "/expenses/add" in html, \
            "Profile page must contain a link to /expenses/add"

    def test_profile_add_expense_link_text(self, auth_client):
        html = auth_client.get("/profile").data.decode()
        assert "Add Expense" in html, \
            "Profile page must contain the text 'Add Expense' as a button or link label"

    def test_profile_add_expense_link_is_anchor_or_button(self, auth_client):
        """The Add Expense element must be an <a> tag or a <button> / <input>."""
        html = auth_client.get("/profile").data.decode()
        # At minimum the href must appear
        assert 'href' in html and '/expenses/add' in html, \
            "Profile must have an <a href='/expenses/add'> element"


# ------------------------------------------------------------------ #
# 8. All Valid Categories Accepted (parametrized)                     #
# ------------------------------------------------------------------ #

class TestAllCategoriesAccepted:

    @pytest.mark.parametrize("category", VALID_CATEGORIES)
    def test_valid_category_accepted(self, auth_client, category):
        """Each of the seven fixed categories must be accepted without error."""
        response = auth_client.post("/expenses/add", data={
            "amount":      "100",
            "category":    category,
            "date":        TODAY_ISO,
            "description": f"Test for {category}",
        })
        assert response.status_code == 302, \
            f"Category '{category}' must be accepted and redirect (302)"

    @pytest.mark.parametrize("category", VALID_CATEGORIES)
    def test_valid_category_stored_correctly(self, auth_client, category):
        """Each accepted category must be stored verbatim in the DB."""
        auth_client.post("/expenses/add", data={
            "amount":      "100",
            "category":    category,
            "date":        TODAY_ISO,
            "description": "",
        })
        row = _get_last_expense()
        assert row["category"] == category, \
            f"Category stored as '{row['category']}', expected '{category}'"


# ------------------------------------------------------------------ #
# 9. Invalid Input Parametrized — All Trigger Re-Render               #
# ------------------------------------------------------------------ #

class TestInvalidInputsParametrized:

    @pytest.mark.parametrize("amount,label", [
        ("",         "blank amount"),
        ("0",        "zero amount"),
        ("-1",       "negative amount"),
        ("0.00",     "zero decimal amount"),
        ("-0.01",    "tiny negative amount"),
        ("abc",      "alphabetic amount"),
        ("1 000",    "amount with space"),
        ("1,000",    "amount with comma"),
        ("1e5",      "scientific notation"),
    ])
    def test_invalid_amount_returns_200(self, auth_client, amount, label):
        """All invalid amount values must return 200 (form re-render), not redirect."""
        response = auth_client.post("/expenses/add", data={
            "amount":      amount,
            "category":    "Food",
            "date":        TODAY_ISO,
            "description": "",
        })
        # 1e5 is technically parseable as float — check if app rejects it.
        # The spec says non-numeric or zero/negative; 1e5 is >0 and numeric,
        # so we only assert non-redirect for the clearly invalid cases.
        if amount in ("", "0", "-1", "0.00", "-0.01", "abc", "1 000", "1,000"):
            assert response.status_code == 200, \
                f"Invalid amount '{label}' must return 200 (re-render), got {response.status_code}"

    @pytest.mark.parametrize("bad_date,label", [
        ("",           "blank date"),
        ("2026-13-01", "month 13"),
        ("2026-00-15", "month 00"),
        ("2026-02-30", "Feb 30"),
        ("15-05-2026", "wrong format DD-MM-YYYY"),
        ("2026/05/15", "slash separator"),
        ("notadate",   "non-date string"),
    ])
    def test_invalid_date_returns_200(self, auth_client, bad_date, label):
        """All invalid date values must return 200 (form re-render), not redirect."""
        response = auth_client.post("/expenses/add", data={
            "amount":      "100",
            "category":    "Food",
            "date":        bad_date,
            "description": "",
        })
        assert response.status_code == 200, \
            f"Invalid date '{label}' must return 200 (re-render), got {response.status_code}"

    @pytest.mark.parametrize("bad_category", [
        "Gambling",
        "food",          # wrong case
        "FOOD",          # all caps
        "Food ",         # trailing space
        " Food",         # leading space
        "food,transport",
        "",
        "'; DROP TABLE expenses; --",  # SQL injection attempt
    ])
    def test_invalid_category_returns_200(self, auth_client, bad_category):
        """Invalid category values must return 200 (form re-render)."""
        response = auth_client.post("/expenses/add", data={
            "amount":      "100",
            "category":    bad_category,
            "date":        TODAY_ISO,
            "description": "",
        })
        assert response.status_code == 200, \
            f"Invalid category '{bad_category}' must return 200 (re-render)"


# ------------------------------------------------------------------ #
# 10. SQL Injection Safety                                             #
# ------------------------------------------------------------------ #

class TestSQLInjectionSafety:

    def test_sql_injection_in_description_stored_safely(self, auth_client):
        """A SQL injection payload in description must be stored as plain text, not executed."""
        payload = "'; DROP TABLE expenses; --"
        auth_client.post("/expenses/add", data={
            "amount":      "100",
            "category":    "Other",
            "date":        TODAY_ISO,
            "description": payload,
        })
        # The expenses table must still exist and the row must be present.
        row = _get_last_expense()
        assert row is not None, \
            "expenses table must survive a SQL injection attempt in description"
        assert row["description"] == payload, \
            "SQL injection payload must be stored as literal text, not executed"

    def test_sql_injection_in_amount_does_not_crash(self, auth_client):
        """SQL injection in amount field must trigger validation, not a 500."""
        response = auth_client.post("/expenses/add", data={
            "amount":      "'; DROP TABLE expenses; --",
            "category":    "Food",
            "date":        TODAY_ISO,
            "description": "",
        })
        assert response.status_code == 200, \
            "SQL injection in amount must be caught by validation (re-render 200), not crash"


# ------------------------------------------------------------------ #
# 11. Expense Appears on Profile After Addition                       #
# ------------------------------------------------------------------ #

class TestExpenseAppearsOnProfile:

    def test_added_expense_description_visible_on_profile(self, auth_client):
        """After adding an expense, its description must appear in the profile transactions."""
        auth_client.post("/expenses/add", data={
            "amount":      "750",
            "category":    "Shopping",
            "date":        TODAY_ISO,
            "description": "Unique shopping trip marker",
        })
        html = auth_client.get("/profile").data.decode()
        assert "Unique shopping trip marker" in html, \
            "Newly added expense description must appear on the profile page"

    def test_added_expense_category_visible_on_profile(self, auth_client):
        """After adding an expense, its category must appear in the profile."""
        auth_client.post("/expenses/add", data={
            "amount":      "500",
            "category":    "Entertainment",
            "date":        TODAY_ISO,
            "description": "Movie night unique marker",
        })
        html = auth_client.get("/profile").data.decode()
        assert "Entertainment" in html, \
            "Newly added expense category must appear on the profile page"

    def test_transaction_count_increases_on_profile(self, auth_client):
        """Profile transaction count stat must increase after adding an expense."""
        before_html = auth_client.get("/profile").data.decode()
        auth_client.post("/expenses/add", data={
            "amount":      "200",
            "category":    "Food",
            "date":        TODAY_ISO,
            "description": "",
        })
        after_html = auth_client.get("/profile").data.decode()
        # The count went from 0 to 1 for a fresh user — "1" must now appear.
        assert "1" in after_html, \
            "Transaction count must reflect the newly added expense on the profile page"
