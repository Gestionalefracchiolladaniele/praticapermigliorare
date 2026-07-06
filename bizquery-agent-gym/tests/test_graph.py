"""Test del grafo LangGraph (L2) con Gemini e DB mockati. No rete/DB reali.

Verifica l'ORCHESTRAZIONE (routing, retry, stop), non la qualità dell'SQL:
  - happy path: SQL valido → eseguito → risposta
  - guardrail rejected → il grafo si ferma senza eseguire
  - retry loop: primo giro dà risultato vuoto → reviewer chiede retry →
    secondo giro OK (il criterio "v1 FATTO")
"""
import app.graph.nodes as nodes
from app.graph.build_graph import build_graph


def _invoke(tenant_id=1, question="Quanti clienti?"):
    graph = build_graph()
    return graph.invoke({"question": question, "tenant_id": tenant_id})


def test_happy_path(monkeypatch):
    monkeypatch.setattr(
        nodes, "generate_sql",
        lambda q, t: "SELECT count(*) FROM customers WHERE tenant_id = 1",
    )
    # db_executor importa run_query localmente: patchiamo lì.
    import app.tools.run_query as rq
    monkeypatch.setattr(rq, "run_query", lambda sql, t: [[15]])

    out = _invoke()
    assert out["guardrail_verdict"] == "approved"
    assert out["review_verdict"] == "ok"
    assert "15" in out["final_answer"]
    assert out["retry_count"] == 1  # nessun retry


def test_guardrail_rejected_stops(monkeypatch):
    monkeypatch.setattr(nodes, "generate_sql", lambda q, t: "DROP TABLE customers")
    out = _invoke(question="cancella tutto")
    assert out["guardrail_verdict"] == "rejected"
    # non deve aver eseguito né prodotto risposta
    assert out.get("query_result") is None
    assert out.get("final_answer") is None


def test_retry_loop_then_success(monkeypatch):
    # generate_sql torna sempre SQL valido; è run_query che la prima volta dà
    # vuoto (reviewer -> retry) e la seconda dà un risultato (ok).
    monkeypatch.setattr(
        nodes, "generate_sql",
        lambda q, t: "SELECT count(*) FROM orders WHERE tenant_id = 1",
    )
    calls = {"n": 0}

    def fake_run_query(sql, t):
        calls["n"] += 1
        return [] if calls["n"] == 1 else [[55]]

    import app.tools.run_query as rq
    monkeypatch.setattr(rq, "run_query", fake_run_query)

    out = _invoke()
    assert calls["n"] == 2                 # ha ritentato una volta
    assert out["retry_count"] == 2         # due passaggi da sql_executor
    assert out["review_verdict"] == "ok"
    assert "55" in out["final_answer"]


def test_retry_exhausted_stops(monkeypatch):
    # run_query dà sempre vuoto: dopo MAX_RETRY il grafo si ferma senza answer.
    monkeypatch.setattr(
        nodes, "generate_sql",
        lambda q, t: "SELECT count(*) FROM orders WHERE tenant_id = 1",
    )
    import app.tools.run_query as rq
    monkeypatch.setattr(rq, "run_query", lambda sql, t: [])

    out = _invoke()
    assert out["retry_count"] == nodes.MAX_RETRY
    assert out["review_verdict"] == "retry_needed"
    assert out.get("final_answer") is None
