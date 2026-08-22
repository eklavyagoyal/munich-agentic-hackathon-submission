"""The dashboard is the one component that puts our data on a screen other people
can see, so the only thing worth pinning is that it cannot put a secret there."""
from __future__ import annotations

from tools.dashboard import scrub


def test_secret_field_names_are_redacted():
    out = scrub({"decryption_key": "x" * 12, "api_key": "k" * 36,
                 "token": "t123", "credentials": "c",
                 "authorization": "Bearer abc"})
    for field, value in out.items():
        assert str(value).startswith("<redacted"), f"{field} leaked: {value}"


def test_authorization_is_redacted_but_author_is_not():
    # `auth(?!or)` used to spare "authorization" along with "author".
    assert scrub({"authorization": "Bearer abc"})["authorization"].startswith("<redacted")
    assert scrub({"author": "luis"})["author"] == "luis"


def test_operational_fields_survive():
    # Redact too eagerly and the dashboard shows nothing useful.
    out = scrub({"case_id": "7", "n_items": 4, "qty": 18, "ms": 140.3})
    assert out == {"case_id": "7", "n_items": 4, "qty": 18, "ms": 140.3}


def test_nested_and_listed_secrets_are_reached():
    out = scrub({"rounds": [{"headers": {"x_api_key": "abc123"}}]})
    assert out["rounds"][0]["headers"]["x_api_key"].startswith("<redacted")
