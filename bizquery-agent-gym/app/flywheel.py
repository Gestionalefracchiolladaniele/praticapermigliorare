"""Data flywheel (Livello 3): logga ogni run e riusa quelle riuscite.

L'idea del flywheel: ogni domanda che l'agente risolve bene è un ESEMPIO. Se
riusiamo le coppie (domanda → SQL) riuscite come few-shot nel prompt del planner,
il modello genera SQL migliore sulle domande simili successive. Più il sistema
gira, più esempi accumula, meglio risponde — un ciclo che si auto-alimenta.

Due funzioni, due direzioni del ciclo:
  - log_run(...)             : scrive in query_logs cosa è successo in una run.
  - successful_examples(...) : rilegge le run RIUSCITE come few-shot per il planner.

Entrambe passano da tenant_session (RLS): un tenant logga e rilegge SOLO i propri
log. Il masking PII vale anche qui — la domanda e l'SQL non contengono email, ma
per sicurezza non logghiamo mai i RISULTATI (che sì conterrebbero PII).
"""
from __future__ import annotations

from app.db.client import tenant_session


def log_run(
    tenant_id: int,
    question: str,
    generated_sql: str | None,
    guardrail_verdict: str | None,
    review_verdict: str | None,
    retry_count: int,
    was_flagged: bool,
    human_approved: bool | None,
    success: bool,
) -> None:
    """Registra una run in query_logs. Non solleva se il DB non c'è: il logging
    è osservabilità, non deve mai far fallire la risposta all'utente."""
    try:
        with tenant_session(tenant_id) as conn:
            conn.execute(
                """
                INSERT INTO query_logs
                    (tenant_id, question, generated_sql, guardrail_verdict,
                     review_verdict, retry_count, was_flagged, human_approved, success)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (tenant_id, question, generated_sql, guardrail_verdict,
                 review_verdict, retry_count, was_flagged, human_approved, success),
            )
            conn.commit()  # a differenza delle SELECT read-only, qui persistiamo
    except Exception:  # noqa: BLE001 — logging best-effort
        pass


def successful_examples(tenant_id: int, limit: int = 3) -> list[tuple[str, str]]:
    """Ritorna le ultime coppie (domanda, sql) di run RIUSCITE per il tenant,
    da usare come few-shot nel prompt del planner. Solo run con success=TRUE e
    un SQL non nullo: un esempio deve essere una query che ha davvero funzionato.

    De-duplica per domanda (una domanda ripetuta non deve occupare più slot) e
    limita a `limit` esempi per non gonfiare il prompt (few-shot, non fine-tuning).
    """
    try:
        with tenant_session(tenant_id) as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT ON (question) question, generated_sql
                FROM query_logs
                WHERE tenant_id = %s AND success = TRUE AND generated_sql IS NOT NULL
                ORDER BY question, created_at DESC
                LIMIT %s
                """,
                (tenant_id, limit),
            ).fetchall()
        return [(q, s) for q, s in rows]
    except Exception:  # noqa: BLE001
        return []
