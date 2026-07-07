"""Test del grafo LangGraph (L2) con Gemini e DB mockati. No rete/DB reali.

Verifica l'ORCHESTRAZIONE (routing, retry, stop), non la qualità dell'SQL:
  - happy path: SQL valido → eseguito → risposta
  - guardrail rejected → il grafo si ferma senza eseguire
  - retry loop: primo giro dà risultato vuoto → reviewer chiede retry →
    secondo giro OK (il criterio "v1 FATTO")
"""
import pytest

import app.graph.nodes as nodes
from app.graph.build_graph import build_graph
from langgraph.types import Command


@pytest.fixture(autouse=True)
def _isolate_external(monkeypatch):
    """I test di orchestrazione non devono toccare Gemini né il DB per i pezzi
    L3 (flywheel, reviewer LLM). Neutralizziamo:
      - successful_examples -> nessun few-shot (non serve un DB)
      - review_answer -> verdetto deterministico su righe (come il vecchio
        reviewer): così questi test verificano il ROUTING, non il giudizio LLM.
    I test che vogliono il reviewer LLM vero lo fanno altrove (live)."""
    monkeypatch.setattr(nodes, "successful_examples", lambda tid, **kw: [])
    monkeypatch.setattr(
        nodes, "review_answer",
        lambda q, sql, rows: "ok" if rows else "retry_needed",
    )


def _invoke(tenant_id=1, question="Quanti clienti?"):
    graph = build_graph()
    # Col checkpointer (aggiunto in L3 per l'human-in-the-loop) ogni run richiede
    # un thread_id: uno diverso per test così sono isolati.
    import uuid
    cfg = {"configurable": {"thread_id": str(uuid.uuid4())}}
    return graph.invoke({"question": question, "tenant_id": tenant_id}, cfg)


def test_happy_path(monkeypatch):
    monkeypatch.setattr(
        nodes, "generate_sql",
        lambda q, t, **kw: "SELECT count(*) FROM customers WHERE tenant_id = 1",
    )
    # db_executor importa run_query localmente: patchiamo lì.
    import app.tools.run_query as rq
    monkeypatch.setattr(rq, "run_query", lambda sql, t, **kw: [[15]])

    out = _invoke()
    assert out["guardrail_verdict"] == "approved"
    assert out["review_verdict"] == "ok"
    assert "15" in out["final_answer"]
    assert out["retry_count"] == 1  # nessun retry


def test_guardrail_rejected_stops(monkeypatch):
    monkeypatch.setattr(nodes, "generate_sql", lambda q, t, **kw: "DROP TABLE customers")
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
        lambda q, t, **kw: "SELECT count(*) FROM orders WHERE tenant_id = 1",
    )
    calls = {"n": 0}

    def fake_run_query(sql, t, **kw):
        calls["n"] += 1
        return [] if calls["n"] == 1 else [[55]]

    import app.tools.run_query as rq
    monkeypatch.setattr(rq, "run_query", fake_run_query)

    out = _invoke()
    assert calls["n"] == 2                 # ha ritentato una volta
    assert out["retry_count"] == 2         # due passaggi da sql_executor
    assert out["review_verdict"] == "ok"
    assert "55" in out["final_answer"]


def test_human_in_the_loop_approve(monkeypatch):
    """Query rischiosa (SELECT righe senza LIMIT) -> guardrail needs_human ->
    il grafo si SOSPENDE (interrupt). Con Command(resume='approve') riprende,
    esegue e risponde. E' il criterio human-in-the-loop di L3."""
    import uuid
    # SQL lecito ma senza LIMIT su selezione di righe -> needs_human.
    monkeypatch.setattr(
        nodes, "generate_sql",
        lambda q, t, **kw: "SELECT * FROM customers WHERE tenant_id = 1",
    )
    import app.tools.run_query as rq
    monkeypatch.setattr(rq, "run_query", lambda sql, t, **kw: [[1], [2], [3]])

    graph = build_graph()
    cfg = {"configurable": {"thread_id": str(uuid.uuid4())}}
    out = graph.invoke({"question": "elenca i clienti", "tenant_id": 1}, cfg)

    # Si è fermato in attesa dell'umano: c'è un interrupt pendente, nessuna risposta.
    assert out.get("__interrupt__")
    assert out.get("final_answer") is None

    # L'umano approva -> il grafo riprende ed esegue.
    out2 = graph.invoke(Command(resume="approve"), cfg)
    assert out2["guardrail_verdict"] == "approved"
    assert out2["human_approved"] is True
    assert out2["final_answer"] is not None


def test_human_in_the_loop_reject(monkeypatch):
    """Stessa sospensione, ma l'umano rifiuta -> il grafo si ferma senza eseguire."""
    import uuid
    monkeypatch.setattr(
        nodes, "generate_sql",
        lambda q, t, **kw: "SELECT * FROM customers WHERE tenant_id = 1",
    )
    graph = build_graph()
    cfg = {"configurable": {"thread_id": str(uuid.uuid4())}}
    graph.invoke({"question": "elenca i clienti", "tenant_id": 1}, cfg)

    out2 = graph.invoke(Command(resume="reject"), cfg)
    assert out2["guardrail_verdict"] == "rejected"
    assert out2["human_approved"] is False
    assert out2.get("final_answer") is None


def test_retry_exhausted_stops(monkeypatch):
    # run_query dà sempre vuoto: dopo MAX_RETRY il grafo si ferma senza answer.
    monkeypatch.setattr(
        nodes, "generate_sql",
        lambda q, t, **kw: "SELECT count(*) FROM orders WHERE tenant_id = 1",
    )
    import app.tools.run_query as rq
    monkeypatch.setattr(rq, "run_query", lambda sql, t, **kw: [])

    out = _invoke()
    assert out["retry_count"] == nodes.MAX_RETRY
    assert out["review_verdict"] == "retry_needed"
    assert out.get("final_answer") is None
