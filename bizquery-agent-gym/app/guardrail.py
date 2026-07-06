"""Guardrail hard-coded per l'SQL generato dall'LLM (step 3 del piano v0).

NON è un agente e NON è LLM: sono regole deterministiche, l'ultima difesa prima
di eseguire SQL prodotto da un modello. La RLS del DB è la difesa vera contro il
cross-tenant leak; questo guardrail è difesa-in-profondità + blocco scritture,
così un prompt injection che facesse generare `DROP TABLE` non arriva mai al DB.

Regole v0 (sottoinsieme delle regole a regime in PROJECT.md):
  1. Sola lettura: una sola statement, e deve essere un SELECT (o WITH...SELECT).
     Qualsiasi DELETE/DROP/UPDATE/INSERT/ALTER/TRUNCATE/... => rejected.
  2. Niente multi-statement (';' che separa più comandi) => rejected, blocca
     lo stacked-query injection ("SELECT ...; DROP TABLE ...").
  3. Deve filtrare per tenant: WHERE ... tenant_id ... deve comparire. Difesa
     aggiuntiva anche se la RLS lo forzerebbe comunque.

A regime (Livello 3) si aggiungono needs_human (righe stimate, LIMIT) e il
controllo PII. Qui il verdetto è binario: approved | rejected.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Keyword che indicano scrittura/DDL: se compaiono come parola-comando la query
# è rifiutata. \b per non beccare sottostringhe (es. "created_at" non è CREATE).
_FORBIDDEN = [
    "insert", "update", "delete", "drop", "alter", "truncate",
    "create", "grant", "revoke", "merge", "call", "copy",
]
_FORBIDDEN_RE = re.compile(
    r"\b(" + "|".join(_FORBIDDEN) + r")\b", re.IGNORECASE
)


@dataclass(frozen=True)
class Verdict:
    approved: bool
    reason: str  # vuoto se approved, altrimenti motivo del rifiuto


def _strip_comments(sql: str) -> str:
    """Rimuove commenti -- e /* */ per non farsi aggirare da keyword nascoste
    o da un WHERE finto messo in un commento."""
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return sql


def _split_statements(sql: str) -> list[str]:
    """Split grezzo sui ';' che non chiudono la sola statement finale.
    Non è un parser SQL completo: per v0 basta rilevare multi-statement."""
    parts = [s.strip() for s in sql.split(";")]
    return [p for p in parts if p]  # scarta stringhe vuote (es. trailing ';')


def check_sql(sql: str) -> Verdict:
    if not sql or not sql.strip():
        return Verdict(False, "SQL vuoto.")

    cleaned = _strip_comments(sql).strip()

    statements = _split_statements(cleaned)
    if len(statements) != 1:
        return Verdict(
            False,
            f"Attesa una sola statement, trovate {len(statements)} "
            "(possibile stacked-query injection).",
        )

    stmt = statements[0]

    # Deve iniziare per SELECT o WITH (CTE che poi fa SELECT). Blocca subito
    # tutto ciò che non è una lettura in testa alla query.
    head = stmt.lstrip("(").lower()
    if not (head.startswith("select") or head.startswith("with")):
        return Verdict(False, "Solo query SELECT sono permesse (agente read-only).")

    # Nessuna keyword di scrittura/DDL ovunque nella query (anche dentro subquery).
    m = _FORBIDDEN_RE.search(stmt)
    if m:
        return Verdict(False, f"Keyword non permessa: '{m.group(1).upper()}'.")

    # Deve filtrare per tenant. Controllo volutamente semplice per v0: la stringa
    # 'tenant_id' deve comparire nella query. Se manca, rifiuta.
    if "tenant_id" not in stmt.lower():
        return Verdict(False, "Query senza filtro tenant_id: rifiutata.")

    return Verdict(True, "")
