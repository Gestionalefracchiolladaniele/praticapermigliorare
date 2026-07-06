"""Tool run_query — esegue SQL SELECT approvato dentro la sessione tenant (RLS).

Estratto come tool riutilizzabile perché serve a due consumatori:
  - il nodo db_executor del grafo LangGraph (Livello 2)
  - il server MCP (Livello 3), che lo espone come tool esterno

Difesa in profondità: RI-VALIDA col guardrail prima di eseguire, anche se il
chiamante dovrebbe averlo già fatto. Un tool che esegue SQL non deve mai fidarsi
di aver ricevuto SQL sicuro: la validazione è sua responsabilità, non solo di chi
lo chiama. (RLS resta la difesa finale a livello DB.)
"""
from __future__ import annotations

from app.guardrail import check_sql


def run_query(sql: str, tenant_id: int) -> list[list]:
    """Esegue una SELECT approvata per il tenant e ritorna le righe (liste).
    Solleva ValueError se il guardrail rifiuta: non si esegue SQL non sicuro."""
    verdict = check_sql(sql)
    if not verdict.approved:
        raise ValueError(f"guardrail: {verdict.reason}")

    # Import locale: psycopg/DB serve solo a runtime reale, non per importare il tool.
    from app.db.client import tenant_session

    with tenant_session(tenant_id) as conn:
        return [list(r) for r in conn.execute(sql).fetchall()]
