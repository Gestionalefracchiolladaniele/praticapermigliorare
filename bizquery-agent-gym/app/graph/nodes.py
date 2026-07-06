"""Nodi del grafo LangGraph (Livello 2).

Principio: ogni nodo AVVOLGE una funzione v0 già scritta e testata. LangGraph
aggiunge solo l'orchestrazione (stato, routing, retry) sopra logica che esiste.
Ecco perché il grafo non butta v0.

Testabilità senza DB/Gemini: i nodi chiamano funzioni importate a livello di
modulo (generate_sql, check_sql, run_query, ...). Nei test si monkeypatchano,
esattamente come già fatto per l'endpoint /ask in v0. Col DB vero (dopo) le
stesse funzioni girano davvero, senza riscrivere i nodi.

Convenzione LangGraph (langgraph 1.2.7): nodo = funzione (state) -> dict coi soli
campi da aggiornare.
"""
from __future__ import annotations

from app.answer import format_answer
from app.guardrail import check_sql
from app.llm.gemini_client import generate_sql
from app.llm.router import route_model
from app.graph.state import AgentState

MAX_RETRY = 2


def planner_node(state: AgentState) -> dict:
    """v1 minimale: il plan è la domanda stessa (nessun LLM planner ancora).
    A regime interpreta/disambigua; qui fa da passo esplicito per il router."""
    return {"plan": state.question}


def router_node(state: AgentState) -> dict:
    """Sceglie il modello (deterministico). Non è un nodo LLM."""
    decision = route_model(state.question, state.plan)
    return {"model": decision.model}


def sql_executor_node(state: AgentState) -> dict:
    """Genera l'SQL. Avvolge generate_sql (Gemini). Il retry ripassa di qui:
    incrementiamo retry_count qui così il loop è visibile nello stato."""
    sql = generate_sql(state.question, state.tenant_id)
    return {"sql_candidate": sql, "retry_count": state.retry_count + 1}


def guardrail_node(state: AgentState) -> dict:
    """Avvolge check_sql (deterministico)."""
    v = check_sql(state.sql_candidate or "")
    return {
        "guardrail_verdict": "approved" if v.approved else "rejected",
        "guardrail_reason": v.reason,
    }


def db_executor_node(state: AgentState) -> dict:
    """Esegue la query approvata. Avvolge run_query (che usa tenant_session).
    Import locale: il DB serve solo qui, non deve rompere l'import del grafo."""
    from app.tools.run_query import run_query

    try:
        rows = run_query(state.sql_candidate or "", state.tenant_id)
        return {"query_result": rows}
    except Exception as e:  # noqa: BLE001
        return {"error": f"esecuzione fallita: {e}"}


def reviewer_node(state: AgentState) -> dict:
    """v1 minimale: la review è deterministica — se c'è un risultato non vuoto,
    ok; altrimenti retry_needed. A regime sarà Gemini Flash che valuta se il
    risultato risponde alla domanda. Isolato così si sostituisce senza toccare
    il grafo."""
    if state.query_result:
        return {"review_verdict": "ok"}
    return {"review_verdict": "retry_needed"}


def answer_node(state: AgentState) -> dict:
    """Avvolge format_answer (risposta NL)."""
    return {"final_answer": format_answer(state.question, state.query_result or [])}
