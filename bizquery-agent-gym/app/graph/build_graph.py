"""Costruzione del grafo LangGraph (Livello 2).

Flusso v1 (sottoinsieme del grafo a regime in PROJECT.md):

    START → planner → router → sql_executor → guardrail
    guardrail --(rejected)--> END (si ferma col motivo)
    guardrail --(approved)--> db_executor → reviewer
    reviewer --(ok)--> answer → END
    reviewer --(retry_needed, retry_count<2)--> sql_executor   [RETRY LOOP]
    reviewer --(retry_needed, retry_count>=2)--> END (fallimento, per flywheel)

Il retry loop è il criterio "v1 FATTO": query sbagliata → reviewer la rifiuta →
secondo tentativo. Qui è cablato coi conditional edges.

Convenzioni verificate su langgraph 1.2.7 (StateGraph, add_conditional_edges,
START/END). Il grafo si compila senza checkpointer per il flusso lineare+retry;
il checkpointer servirà solo quando aggiungeremo interrupt/human-in-the-loop (L3).
"""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END

from app.graph.state import AgentState
from app.graph import nodes


def _route_after_guardrail(state: AgentState) -> str:
    if state.guardrail_verdict == "approved":
        return "db_executor"
    if state.guardrail_verdict == "needs_human":
        return "human_review"   # sospende (interrupt) e aspetta l'umano
    return END  # rejected → stop


def _route_after_human(state: AgentState) -> str:
    # Dopo la decisione umana: approvata → esegue; rifiutata → stop.
    if state.guardrail_verdict == "approved":
        return "db_executor"
    return END


def _route_after_reviewer(state: AgentState) -> str:
    if state.review_verdict == "ok":
        return "answer"
    if state.retry_count < nodes.MAX_RETRY:
        return "sql_executor"   # ritenta
    return END  # arreso dopo MAX_RETRY


def build_graph():
    """Ritorna il grafo compilato, pronto per .invoke({...})."""
    g = StateGraph(AgentState)

    g.add_node("planner", nodes.planner_node)
    g.add_node("router", nodes.router_node)
    g.add_node("sql_executor", nodes.sql_executor_node)
    g.add_node("guardrail", nodes.guardrail_node)
    g.add_node("human_review", nodes.human_review_node)
    g.add_node("db_executor", nodes.db_executor_node)
    g.add_node("reviewer", nodes.reviewer_node)
    g.add_node("answer", nodes.answer_node)

    g.add_edge(START, "planner")
    g.add_edge("planner", "router")
    g.add_edge("router", "sql_executor")
    g.add_edge("sql_executor", "guardrail")
    g.add_conditional_edges("guardrail", _route_after_guardrail)
    g.add_conditional_edges("human_review", _route_after_human)
    g.add_edge("db_executor", "reviewer")
    g.add_conditional_edges("reviewer", _route_after_reviewer)
    g.add_edge("answer", END)

    # Checkpointer: serve perché interrupt() (human_review) persista lo stato tra
    # la sospensione e la ripresa. MemorySaver = in-process, ok per v0/single
    # istanza; a regime (multi-worker) si userebbe un checkpointer su Postgres.
    return g.compile(checkpointer=MemorySaver())


# Singleton: /ask-graph e /approve DEVONO condividere lo stesso checkpointer
# (MemorySaver in-process), altrimenti la ripresa non ritrova lo stato sospeso.
# Un solo grafo compilato per processo. I test che vogliono isolamento usano
# build_graph() direttamente.
_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH
