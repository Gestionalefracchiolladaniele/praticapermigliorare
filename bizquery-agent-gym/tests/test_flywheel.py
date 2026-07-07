"""Test del data flywheel (L3): logging + rilettura, con isolamento RLS.

Serve un DB reale (query_logs con RLS). Si skippa senza DATABASE_URL, come gli
altri test che toccano il DB. Ogni test usa un marcatore univoco nella domanda
per non dipendere dai log lasciati da altri test/run.
"""
import os
import uuid

import pytest

from app.flywheel import log_run, successful_examples

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="serve un Postgres reale su localhost:5432 (DATABASE_URL non impostata)",
)


def test_log_and_read_back():
    """Una run loggata con success=True torna tra i few-shot del suo tenant."""
    marker = f"test-flywheel-{uuid.uuid4()}"
    sql = "SELECT count(id) FROM customers WHERE tenant_id = 1"
    log_run(
        tenant_id=1, question=marker, generated_sql=sql,
        guardrail_verdict="approved", review_verdict="ok", retry_count=1,
        was_flagged=False, human_approved=None, success=True,
    )
    examples = successful_examples(1, limit=50)
    questions = [q for q, _ in examples]
    assert marker in questions


def test_failed_run_not_used_as_example():
    """Una run con success=False NON deve diventare un few-shot."""
    marker = f"test-flywheel-fail-{uuid.uuid4()}"
    log_run(
        tenant_id=1, question=marker, generated_sql="SELECT 1 WHERE tenant_id=1",
        guardrail_verdict="approved", review_verdict="retry_needed", retry_count=2,
        was_flagged=False, human_approved=None, success=False,
    )
    questions = [q for q, _ in successful_examples(1, limit=50)]
    assert marker not in questions


def test_logs_isolated_per_tenant():
    """RLS su query_logs: un log del tenant 1 non compare tra gli esempi del 2."""
    marker = f"test-flywheel-iso-{uuid.uuid4()}"
    log_run(
        tenant_id=1, question=marker, generated_sql="SELECT count(id) FROM customers WHERE tenant_id = 1",
        guardrail_verdict="approved", review_verdict="ok", retry_count=1,
        was_flagged=False, human_approved=None, success=True,
    )
    questions_t2 = [q for q, _ in successful_examples(2, limit=50)]
    assert marker not in questions_t2
