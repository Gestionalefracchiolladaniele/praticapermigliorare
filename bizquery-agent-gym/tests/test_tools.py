"""Test dei tool L2/L3 (mask_pii, send_notification, run_query). No DB reale."""
from app.tools.mask_pii import mask_email, mask_pii_in_rows
from app.tools.send_notification import send_notification, sent_notifications
from app.tools.run_query import run_query


def test_mask_email_hides_identity_keeps_domain():
    assert mask_email("marco.rossi@example.com") == "m***@example.com"


def test_mask_email_leaves_non_email():
    assert mask_email("Marco Rossi") == "Marco Rossi"


def test_mask_rows_only_touches_emails():
    rows = [["Marco Rossi", "marco.rossi@example.com", 42]]
    out = mask_pii_in_rows(rows)
    assert out == [["Marco Rossi", "m***@example.com", 42]]


def test_send_notification_records():
    before = len(sent_notifications())
    res = send_notification("a@b.com", "test", "corpo")
    assert res["ok"] is True
    assert res["delivered"] is False       # stub
    assert len(sent_notifications()) == before + 1


def test_run_query_rejects_dangerous_sql():
    # Non deve nemmeno provare a connettersi al DB: il guardrail blocca prima.
    import pytest
    with pytest.raises(ValueError):
        run_query("DROP TABLE customers", 1)
