"""Stato condiviso del grafo LangGraph (Livello 2).

Sottoinsieme v1 dell'AgentState a regime (PROJECT.md): solo i campi che i nodi
del grafo v1 usano davvero (planner→sql_executor→guardrail→db_executor→reviewer,
con retry loop). Gli altri (chat_history, cost, human_approved, trace_id) si
aggiungono ai nodi L2/L3 successivi.

Pydantic e non TypedDict: coerente con lo stack (usiamo già pydantic), dà
validazione dei tipi. LangGraph supporta entrambi.

Convenzione LangGraph (verificata su langgraph 1.2.7): un nodo riceve lo stato e
ritorna un dict coi SOLI campi da aggiornare. Qui i campi non hanno reducer:
l'ultimo aggiornamento vince (va bene, ogni nodo scrive campi diversi).
"""
from __future__ import annotations

from pydantic import BaseModel


class AgentState(BaseModel):
    # input
    question: str
    tenant_id: int

    # prodotti dai nodi (opzionali finché il nodo relativo non li riempie)
    plan: str | None = None
    model: str | None = None            # scelto dal router
    sql_candidate: str | None = None
    guardrail_verdict: str | None = None   # "approved" | "rejected"
    guardrail_reason: str | None = None
    query_result: list | None = None
    review_verdict: str | None = None      # "ok" | "retry_needed"
    retry_count: int = 0
    human_approved: bool | None = None     # esito revisione umana (L3), se avvenuta
    final_answer: str | None = None
    error: str | None = None               # se un nodo fallisce, si ferma con motivo
