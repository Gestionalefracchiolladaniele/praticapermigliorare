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

# Funzioni/costrutti pericolosi che NON contengono keyword di scrittura ma
# leggono/scrivono il filesystem o il sistema del server, fanno DoS, o
# spoofano il tenant. Il red-team (2026-07-14) le ha trovate: passavano perché
# sono "SELECT read-only con tenant_id nella stringa". Un agente BI legittimo non
# le chiama MAI → blocklist esplicita, verdetto rejected.
#   pg_read_file/ls_dir/stat_file : leggono il filesystem del server (esfiltrazione)
#   lo_import/lo_export/lo_*       : import/export di large object su file (scrittura!)
#   pg_sleep                       : DoS / blind-timing injection
#   current_setting/set_config     : leggono/scrivono app.tenant_id → spoof del tenant
#   dblink, copy ... program       : eseguono verso l'esterno / comandi di sistema
_DANGEROUS_FUNCS = [
    "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "pg_stat_file",
    "pg_read_server_files", "pg_execute_server_program",
    "lo_import", "lo_export", "lo_get", "lo_put", "lo_from_bytea",
    "dblink", "dblink_exec",
    "pg_sleep", "pg_sleep_for", "pg_sleep_until",
    "current_setting", "set_config",
]
_DANGEROUS_RE = re.compile(
    r"\b(" + "|".join(_DANGEROUS_FUNCS) + r")\b", re.IGNORECASE
)

# Filtro tenant REALE. Non basta che la stringa 'tenant_id' compaia: il red-team
# l'ha bucato con `SELECT tenant_id, email FROM customers` (nel SELECT-list),
# `name AS tenant_id` (alias), `WHERE name = 'tenant_id'` (stringa letterale) —
# tutti SENZA un vero filtro. Serve un PREDICATO: tenant_id confrontato con
# = / IN / BETWEEN. Non è un parser SQL, è un'euristica più stretta che alza
# molto l'asticella. La difesa DEFINITIVA resta la RLS del DB (vedi nota in fondo).
_TENANT_PREDICATE_RE = re.compile(
    r"\btenant_id\b\s*(=|in\b|between\b)", re.IGNORECASE
)

# Set-operation: ogni ramo di UNION/INTERSECT/EXCEPT deve avere il proprio filtro
# tenant. `... WHERE tenant_id=1 UNION SELECT email FROM customers` ha il filtro
# solo nel primo ramo: il secondo legge tutto. Splittiamo sui set-operator (fuori
# da parentesi non lo distinguiamo — euristica v0) e validiamo ogni ramo.
_SETOP_SPLIT_RE = re.compile(r"\b(?:union|intersect|except)\b(?:\s+all)?", re.IGNORECASE)


@dataclass(frozen=True)
class Verdict:
    approved: bool
    reason: str  # vuoto se approved, altrimenti motivo del rifiuto
    # Livello 3: oltre a approved/rejected, una query può essere LECITA ma
    # RISCHIOSA (es. nessun LIMIT su una potenziale scansione ampia) → non si
    # blocca né si esegue: si chiede a un umano. `needs_human=True` implica
    # approved=False (non è passata liberamente) ma reason spiega che è
    # sospesa, non rifiutata.
    needs_human: bool = False


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

    # Funzioni pericolose (esfiltrazione filesystem, DoS, spoof tenant): rejected.
    # Chiude i bypass del red-team che non usano keyword di scrittura (pg_read_file,
    # lo_export, pg_sleep, current_setting).
    d = _DANGEROUS_RE.search(stmt)
    if d:
        return Verdict(False, f"Funzione non permessa: '{d.group(1).lower()}()'.")

    # Deve filtrare per tenant — con un vero PREDICATO, non la sola presenza della
    # stringa 'tenant_id' (bypassabile da alias/stringa/SELECT-list). Inoltre, se
    # la query è una set-operation (UNION/INTERSECT/EXCEPT), OGNI ramo deve avere
    # il proprio filtro: un ramo senza filtro leggerebbe tutto. Nota: split
    # euristico v0 (non distingue un UNION dentro una subquery in parentesi) —
    # scelta conservativa: nel dubbio richiede il filtro in ogni pezzo.
    branches = _SETOP_SPLIT_RE.split(stmt)
    for branch in branches:
        if not _TENANT_PREDICATE_RE.search(branch):
            return Verdict(
                False,
                "Query senza filtro tenant_id valido (serve 'tenant_id = ...' in "
                "ogni ramo): rifiutata.",
            )

    # Livello 3 — needs_human: la query è sicura (read-only, single-statement,
    # con tenant), ma potenzialmente RISCHIOSA. Caso mirato: `SELECT *` senza
    # LIMIT — prende TUTTE le colonne (incluse eventuali PII) su TUTTE le righe.
    # Non la blocchiamo (è lecita) ma chiediamo conferma umana. Selezioni di
    # colonne specifiche, o con LIMIT, o aggregazioni passano senza intervento:
    # la regola resta stretta per non disturbare le query normali.
    low = stmt.lower()
    selects_star = bool(re.search(r"select\s+\*", low))
    has_limit = bool(re.search(r"\blimit\b", low))
    # Se ovunque nella query c'è un'aggregazione (anche una CTE che fa SELECT *
    # ma poi count(*)), il risultato finale è piccolo → non è il caso rischioso.
    is_aggregate = bool(re.search(r"\b(count|sum|avg|min|max)\s*\(|\bgroup by\b", low))
    if selects_star and not has_limit and not is_aggregate:
        return Verdict(
            False,
            "SELECT * senza LIMIT: legge tutte le colonne (possibili PII) e tutte "
            "le righe. Richiede approvazione umana.",
            needs_human=True,
        )

    return Verdict(True, "")
