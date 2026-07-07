"""Test del grafo LangGraph (L2) DAL VIVO: retry loop contro Postgres reale.

Differenza da test_graph.py (tutto mockato): qui run_query gira DAVVERO sul DB
(RLS + tenant_session). Mockiamo solo generate_sql — non per evitare il DB, ma
per non spendere chiamate Gemini e per controllare il primo SQL (che deve dare
risultato vuoto) e il secondo (che deve dare righe). Così il RETRY LOOP passa
per l'esecuzione reale: primo giro 0 righe -> reviewer chiede retry -> secondo
giro righe vere -> ok. E' il criterio "v1 FATTO" verificato end-to-end col DB.

Si skippa se non c'e' un Postgres su localhost:5432 (come test_rls_isolation).
"""
import os

import pytest

import app.graph.nodes as nodes
from app.graph.build_graph import build_graph

# Senza DATABASE_URL non c'e' DB reale: skip (come gli altri test che serve il DB).
pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="serve un Postgres reale su localhost:5432 (DATABASE_URL non impostata)",
)


def test_retry_loop_live_against_real_db(monkeypatch):
    """Primo SQL: conteggio su un tenant che nel seed non ha righe di quel tipo
    -> 0 -> retry. Secondo SQL: conteggio valido -> righe -> ok. run_query
    esegue DAVVERO sul Postgres del container."""
    calls = {"n": 0}

    def fake_generate_sql(question, tenant_id):
        calls["n"] += 1
        if calls["n"] == 1:
            # Query sintatticamente valida e approvata dal guardrail, ma che
            # ritorna 0 righe: WHERE su un valore inesistente.
            return ("SELECT id FROM customers "
                    "WHERE tenant_id = 1 AND country = 'ZZ_INESISTENTE'")
        # Secondo tentativo: query valida con risultato reale.
        return "SELECT count(id) FROM customers WHERE tenant_id = 1"

    monkeypatch.setattr(nodes, "generate_sql", fake_generate_sql)

    graph = build_graph()
    import uuid
    cfg = {"configurable": {"thread_id": str(uuid.uuid4())}}
    out = graph.invoke({"question": "Quanti clienti abbiamo?", "tenant_id": 1}, cfg)

    assert calls["n"] == 2                 # ha rigenerato l'SQL una volta (retry)
    assert out["retry_count"] == 2         # due passaggi da sql_executor
    assert out["review_verdict"] == "ok"   # il secondo giro ha prodotto righe
    assert out["final_answer"] is not None
